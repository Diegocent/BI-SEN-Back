# -*- coding: utf-8 -*-
"""Carga ÚNICA de la planilla histórica hacia la tabla de ingesta.

Este script se ejecuta una sola vez, durante la puesta en marcha del sistema de
ingesta. Migra los registros históricos de `registros_historicos.xlsx` a la
tabla transaccional `ingesta_asistencia_humanitaria`, que a partir de entonces
queda como única fuente de verdad del Data Warehouse.

Por qué existe
--------------
El ETL recurrente (`etl_script.py`) ya no lee Excel: lee la tabla de ingesta. Si
el histórico no se migrara a esa tabla, la primera corrida del ETL dejaría el
Data Warehouse con solo los registros nuevos y se perderían seis años de serie.

Si la fuente son los consolidados anuales 2018–2024 (una fila por titular, con
sexo e indígena), use `cargar_consolidados_a_ingesta.py` y no este script: las
dos cargas se solapan en 2018–2023.

Caracterización de beneficiarios
--------------------------------
Las columnas `cantidad_familias_asistidas`, `sexo_titular` y
`es_poblacion_rural` se cargan en NULL. La planilla histórica no releva esos
datos y no existe forma de inferirlos: dejarlos nulos declara honestamente que
no fueron informados, en lugar de simular un valor. Los registros quedan
marcados con `origen = 'EXCEL_HISTORICO'`, lo que además los exime de la
restricción de completitud que sí rige para las cargas por formulario.

Uso
---
    python etl/cargar_historico_a_ingesta.py --archivo registros_historicos.xlsx

    # Repetir la carga descartando lo importado antes:
    python etl/cargar_historico_a_ingesta.py --reemplazar

    # Ensayo sin escribir en la base:
    python etl/cargar_historico_a_ingesta.py --simular
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from data_cleaner import DataCleaner

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre',
    11: 'Noviembre', 12: 'Diciembre',
}

ORIGEN_HISTORICO = 'EXCEL_HISTORICO'
EVENTO_SENTENCIA = 'C.I.D.H.'
SIN_ESPECIFICAR = 'SIN ESPECIFICAR'

# Cotas de la tabla destino. Se verifican acá para poder reportar el problema
# con contexto, en lugar de recibir un error opaco desde PostgreSQL.
LARGO_MAXIMO = {'departamento': 20, 'distrito': 60, 'localidad': 120}

# Piso de fecha que acepta la tabla para registros históricos.
FECHA_MINIMA_HISTORICA = pd.Timestamp('1990-01-01')

INSUMOS = (
    ('kit_a', 'KIT_A'),
    ('kit_b', 'KIT_B'),
    ('chapa_fibrocemento', 'CHAPA_FIBROCEMENTO'),
    ('chapa_zinc', 'CHAPA_ZINC'),
    ('colchones', 'COLCHONES'),
    ('frazadas', 'FRAZADAS'),
    ('terciadas', 'TERCIADAS'),
    ('puntales', 'PUNTALES'),
    ('carpas_plasticas', 'CARPAS_PLASTICAS'),
)

# Columnas que se envían como parámetros, en el mismo orden en que las arma
# `transformar`. Las marcas temporales no van acá: las pone la base con now().
COLUMNAS_DESTINO = (
    'fecha', 'departamento', 'distrito', 'localidad', 'es_poblacion_rural',
    'evento', 'sexo_titular', 'cantidad_familias_asistidas',
    *[destino for destino, _ in INSUMOS],
    'observaciones', 'anio', 'mes', 'nombre_mes', 'orden_departamento',
    'kit_sentencia', 'kit_evento', 'total_insumos', 'origen',
)

# `creado_por` queda en NULL: ningún usuario cargó estos registros, los aportó
# la planilla histórica.
COLUMNAS_TEMPORALES = ('creado_en', 'actualizado_en')


def conectar():
    """Abre la conexión al PostgreSQL que aloja el DW y la tabla de ingesta."""
    try:
        from dotenv import load_dotenv
        for candidato in (
            Path(__file__).resolve().parent / '.env',
            Path(__file__).resolve().parent.parent / '.env',
        ):
            if candidato.exists():
                load_dotenv(candidato)
                break
    except ImportError:
        pass

    return psycopg2.connect(
        dbname=os.environ.get('DB_DW_NAME', 'data_warehouse'),
        user=os.environ['DB_DW_USER'],
        password=os.environ['DB_DW_PASS'],
        host=os.environ.get('DB_DW_HOST', 'localhost'),
        port=os.environ.get('DB_DW_PORT', '5432'),
        sslmode=os.environ.get('DB_DW_SSLMODE', 'require'),
    )


def extraer(ruta, hoja='Hoja 1'):
    """Lee la planilla histórica."""
    camino = Path(ruta)
    if not camino.exists():
        camino = Path(__file__).resolve().parent.parent / ruta
    if not camino.exists():
        raise FileNotFoundError(f'No se encontró la planilla: {ruta}')

    print(f'🔍 Extrayendo datos desde: {camino}')
    df = pd.read_excel(camino, sheet_name=hoja)
    print(f'✅ {len(df)} filas leídas.')
    return df


def transformar(df):
    """Aplica el pipeline de limpieza histórico y arma las filas destino.

    Reutiliza `DataCleaner` sin modificaciones: es el mismo criterio de
    estandarización con el que se construyó la serie del tablero, y cambiarlo
    ahora produciría un corte en los datos históricos.
    """
    print('\n🧹 Aplicando el pipeline de limpieza histórico...')
    limpio = DataCleaner().run_complete_correction_pipeline(df)

    descartes = {'fecha_invalida': 0, 'sin_insumos': 0, 'texto_excedido': 0}
    filas = []

    for registro in limpio.to_dict('records'):
        fecha = registro.get('FECHA')
        if pd.isna(fecha) or fecha < FECHA_MINIMA_HISTORICA:
            descartes['fecha_invalida'] += 1
            continue

        cantidades = {
            destino: int(registro.get(origen, 0) or 0)
            for destino, origen in INSUMOS
        }
        total_insumos = sum(cantidades.values())
        if total_insumos <= 0:
            descartes['sin_insumos'] += 1
            continue

        geografia = {
            'departamento': str(registro.get('DEPARTAMENTO') or SIN_ESPECIFICAR),
            'distrito': str(registro.get('DISTRITO') or SIN_ESPECIFICAR),
            'localidad': str(registro.get('LOCALIDAD') or SIN_ESPECIFICAR),
        }
        if any(
            len(geografia[campo]) > tope for campo, tope in LARGO_MAXIMO.items()
        ):
            descartes['texto_excedido'] += 1
            print(f'  ⚠️ Texto geográfico demasiado largo, fila omitida: {geografia}')
            continue

        evento = str(registro.get('EVENTO') or 'SIN EVENTO')
        total_kits = cantidades['kit_a'] + cantidades['kit_b']
        es_sentencia = evento == EVENTO_SENTENCIA

        filas.append(
            (
                fecha.date(),
                geografia['departamento'],
                geografia['distrito'],
                geografia['localidad'],
                None,  # es_poblacion_rural: no relevado en el histórico
                evento,
                None,  # sexo_titular: no relevado en el histórico
                None,  # cantidad_familias_asistidas: no relevada
                *[cantidades[destino] for destino, _ in INSUMOS],
                '',  # observaciones
                int(fecha.year),
                int(fecha.month),
                MESES_ES[int(fecha.month)],
                int(registro.get('ORDEN_DEPARTAMENTO', 0) or 0),
                total_kits if es_sentencia else 0,
                0 if es_sentencia else total_kits,
                total_insumos,
                ORIGEN_HISTORICO,
            )
        )

    print(f'\n✅ {len(filas)} filas listas para importar.')
    for motivo, cantidad in descartes.items():
        if cantidad:
            print(f'  ⚠️ Descartadas por {motivo}: {cantidad}')

    return filas


def cargar(conexion, filas, reemplazar):
    """Inserta las filas en la tabla de ingesta dentro de una transacción."""
    from refresco_dw import pausar as pausar_refresco
    with conexion.cursor() as cursor:
        pausar_refresco(cursor, True)
        try:
            cursor.execute(
                'SELECT count(*) FROM ingesta_asistencia_humanitaria WHERE origen = %s;',
                (ORIGEN_HISTORICO,),
            )
            ya_importados = cursor.fetchone()[0]

            if ya_importados and not reemplazar:
                raise SystemExit(
                    f'🛑 Ya existen {ya_importados} registros históricos importados. '
                    'Use --reemplazar para descartarlos y volver a cargar.'
                )

            if ya_importados:
                print(f'🧹 Eliminando {ya_importados} registros históricos previos...')
                cursor.execute(
                    'DELETE FROM ingesta_asistencia_humanitaria WHERE origen = %s;',
                    (ORIGEN_HISTORICO,),
                )

            columnas = (*COLUMNAS_DESTINO, *COLUMNAS_TEMPORALES)
            plantilla = (
                '(' + ', '.join(['%s'] * len(COLUMNAS_DESTINO)) + ', now(), now())'
            )
            execute_values(
                cursor,
                f'INSERT INTO ingesta_asistencia_humanitaria '
                f'({", ".join(columnas)}) VALUES %s',
                filas,
                template=plantilla,
                page_size=1000,
            )
        finally:
            pausar_refresco(cursor, False)

    conexion.commit()
    print(f'✅ {len(filas)} registros históricos importados.')


def verificar(conexion):
    """Informa el estado de la tabla luego de la carga."""
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT origen,
                   count(*),
                   min(fecha),
                   max(fecha),
                   count(sexo_titular),
                   sum(total_insumos)
              FROM ingesta_asistencia_humanitaria
             GROUP BY origen
             ORDER BY origen;
            """
        )
        print('\n📊 Estado de la tabla de ingesta:')
        print(f'{"Origen":<18}{"Filas":>10}{"Desde":>13}{"Hasta":>13}'
              f'{"Con sexo":>11}{"Insumos":>12}')
        for origen, filas, desde, hasta, con_sexo, insumos in cursor.fetchall():
            print(f'{origen:<18}{filas:>10,}{str(desde):>13}{str(hasta):>13}'
                  f'{con_sexo:>11,}{(insumos or 0):>12,}')


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('--archivo', default='registros_historicos.xlsx')
    analizador.add_argument('--hoja', default='Hoja 1')
    analizador.add_argument(
        '--reemplazar',
        action='store_true',
        help='Descarta los registros históricos ya importados antes de cargar.',
    )
    analizador.add_argument(
        '--simular',
        action='store_true',
        help='Procesa la planilla y reporta, sin escribir en la base.',
    )
    argumentos = analizador.parse_args()

    filas = transformar(extraer(argumentos.archivo, argumentos.hoja))
    if not filas:
        print('🛑 No hay filas para importar.')
        return 1

    if argumentos.simular:
        print('\nℹ️ Simulación: no se escribió nada en la base de datos.')
        print(f'   Primera fila que se insertaría: {filas[0][:8]}')
        return 0

    conexion = conectar()
    try:
        cargar(conexion, filas, argumentos.reemplazar)
        verificar(conexion)
    except Exception as error:
        conexion.rollback()
        print(f'\n🛑 Importación fallida, se revirtió la transacción: {error}')
        return 1
    finally:
        conexion.close()

    print('\n🎉 Histórico migrado. Ya puede ejecutarse etl_script.py.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
