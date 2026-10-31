# -*- coding: utf-8 -*-
"""Carga inicial de los consolidados anuales hacia la tabla de ingesta.

Sustituye a `cargar_historico_a_ingesta.py` cuando la fuente son las planillas
CONSOLIDADO 2018–2024 (una fila = un titular). No hay que correr ambos: el
histórico agregado duplicaría 2018–2023.

    python etl/cargar_consolidados_a_ingesta.py --simular
    python etl/cargar_consolidados_a_ingesta.py --anio 2018 --simular
    python etl/cargar_consolidados_a_ingesta.py --reemplazar
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

from mapeo_consolidados import leer_consolidados

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    import psycopg as psycopg2
    execute_values = None

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre',
    11: 'Noviembre', 12: 'Diciembre',
}

ORIGEN_HISTORICO = 'EXCEL_HISTORICO'
EVENTO_SENTENCIA = 'C.I.D.H.'
LARGO_MAXIMO = {'departamento': 20, 'distrito': 60, 'localidad': 120}

COLUMNAS_DESTINO = (
    'fecha', 'departamento', 'distrito', 'localidad',
    'es_poblacion_rural', 'es_poblacion_indigena',
    'evento', 'sexo_titular', 'cantidad_familias_asistidas',
    'kit_a', 'kit_b', 'chapa_fibrocemento', 'chapa_zinc',
    'colchones', 'frazadas', 'terciadas', 'puntales', 'carpas_plasticas',
    'observaciones', 'anio', 'mes', 'nombre_mes', 'orden_departamento',
    'kit_sentencia', 'kit_evento', 'total_insumos', 'origen',
)


def conectar():
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

    host = os.environ.get('DB_DW_HOST', '127.0.0.1')
    sslmode = os.environ.get('DB_DW_SSLMODE')
    if not sslmode:
        sslmode = 'disable' if host in ('localhost', '127.0.0.1', '::1') else 'require'

    return psycopg2.connect(
        dbname=os.environ.get('DB_DW_NAME', 'sen_dw_dev'),
        user=os.environ['DB_DW_USER'],
        password=os.environ['DB_DW_PASS'],
        host=host,
        port=os.environ.get('DB_DW_PORT', '5434'),
        sslmode=sslmode,
    )


def _nulo(valor):
    """Convierte NaN/NA de pandas en None para PostgreSQL."""
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    return valor


def transformar(df: pd.DataFrame) -> list[tuple]:
    filas = []
    texto_excedido = 0
    for registro in df.to_dict('records'):
        fecha = registro['FECHA']
        geografia = {
            'departamento': str(registro.get('DEPARTAMENTO') or 'SIN ESPECIFICAR')[:20],
            'distrito': str(registro.get('DISTRITO') or 'SIN ESPECIFICAR')[:60],
            'localidad': str(registro.get('LOCALIDAD') or 'SIN ESPECIFICAR')[:120],
        }
        if any(
            len(str(registro.get(campo.upper(), ''))) > tope
            for campo, tope in LARGO_MAXIMO.items()
        ):
            texto_excedido += 1

        evento = str(registro.get('EVENTO') or 'SIN EVENTO')[:30]
        kit_a = int(registro.get('KIT_A') or 0)
        kit_b = int(registro.get('KIT_B') or 0)
        insumos = {
            'chapa_fibrocemento': int(registro.get('CHAPA_FIBROCEMENTO') or 0),
            'chapa_zinc': int(registro.get('CHAPA_ZINC') or 0),
            'colchones': int(registro.get('COLCHONES') or 0),
            'frazadas': int(registro.get('FRAZADAS') or 0),
            'terciadas': int(registro.get('TERCIADAS') or 0),
            'puntales': int(registro.get('PUNTALES') or 0),
            'carpas_plasticas': int(registro.get('CARPAS_PLASTICAS') or 0),
        }
        total_kits = kit_a + kit_b
        total_insumos = total_kits + sum(insumos.values())
        es_sentencia = evento == EVENTO_SENTENCIA
        fecha_d = fecha.date() if hasattr(fecha, 'date') else fecha

        filas.append((
            fecha_d,
            geografia['departamento'],
            geografia['distrito'],
            geografia['localidad'],
            None,  # rural: no viene en los consolidados
            _nulo(registro.get('ES_POBLACION_INDIGENA')),
            evento,
            _nulo(registro.get('SEXO')),
            1,  # un titular = una familia
            kit_a,
            kit_b,
            insumos['chapa_fibrocemento'],
            insumos['chapa_zinc'],
            insumos['colchones'],
            insumos['frazadas'],
            insumos['terciadas'],
            insumos['puntales'],
            insumos['carpas_plasticas'],
            '',
            int(fecha_d.year),
            int(fecha_d.month),
            MESES_ES[int(fecha_d.month)],
            int(registro.get('ORDEN_DEPARTAMENTO') or 0),
            total_kits if es_sentencia else 0,
            0 if es_sentencia else total_kits,
            total_insumos,
            ORIGEN_HISTORICO,
        ))

    print(f'\n{len(filas):,} filas listas para importar.')
    if texto_excedido:
        print(f'  Aviso: {texto_excedido:,} textos geográficos se recortaron al tope de columna.')
    return filas


def _resumen_mapeo(df: pd.DataFrame) -> None:
    print('\nSexo:')
    print(df['SEXO'].value_counts(dropna=False).to_string())
    print('\nPoblación indígena:')
    print(df['ES_POBLACION_INDIGENA'].value_counts(dropna=False).to_string())
    print('\nEventos:')
    print(df['EVENTO'].value_counts().head(15).to_string())
    print('\nPor año:')
    print(df['FECHA'].dt.year.value_counts().sort_index().to_string())


def cargar(conexion, filas, reemplazar):
    from refresco_dw import pausar as pausar_refresco
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'ingesta_asistencia_humanitaria'
               AND column_name = 'es_poblacion_indigena';
            """
        )
        if cursor.fetchone() is None:
            raise SystemExit(
                'Falta la columna es_poblacion_indigena. '
                'Ejecute migrate en ingesta_sen y el SQL 002 del esquema estrella.'
            )

        pausar_refresco(cursor, True)
        try:
            cursor.execute(
                'SELECT count(*) FROM ingesta_asistencia_humanitaria WHERE origen = %s;',
                (ORIGEN_HISTORICO,),
            )
            ya_importados = cursor.fetchone()[0]
            if ya_importados and not reemplazar:
                raise SystemExit(
                    f'Ya existen {ya_importados} registros históricos. '
                    'Use --reemplazar para descartarlos y volver a cargar.'
                )
            if ya_importados:
                print(f'Eliminando {ya_importados} registros históricos previos...')
                cursor.execute(
                    'DELETE FROM ingesta_asistencia_humanitaria WHERE origen = %s;',
                    (ORIGEN_HISTORICO,),
                )

            columnas = (*COLUMNAS_DESTINO, 'creado_en', 'actualizado_en')
            plantilla = '(' + ', '.join(['%s'] * len(COLUMNAS_DESTINO)) + ', now(), now())'
            sql = (
                f'INSERT INTO ingesta_asistencia_humanitaria '
                f'({", ".join(columnas)}) VALUES %s'
            )
            if execute_values is not None:
                execute_values(cursor, sql, filas, template=plantilla, page_size=1000)
            else:
                cursor.executemany(
                    sql.replace('VALUES %s', f'VALUES {plantilla}'),
                    filas,
                )
        finally:
            pausar_refresco(cursor, False)

    conexion.commit()
    print(f'{len(filas):,} registros importados.')


def verificar(conexion):
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT origen,
                   count(*),
                   min(fecha),
                   max(fecha),
                   count(sexo_titular),
                   count(es_poblacion_indigena),
                   sum(total_insumos)
              FROM ingesta_asistencia_humanitaria
             GROUP BY origen
             ORDER BY origen;
            """
        )
        print('\nEstado de la tabla de ingesta:')
        print(f'{"Origen":<18}{"Filas":>10}{"Desde":>13}{"Hasta":>13}'
              f'{"Con sexo":>11}{"Indígena":>11}{"Insumos":>12}')
        for origen, filas, desde, hasta, con_sexo, indigena, insumos in cursor.fetchall():
            print(f'{origen:<18}{filas:>10,}{str(desde):>13}{str(hasta):>13}'
                  f'{con_sexo:>11,}{indigena:>11,}{(insumos or 0):>12,}')


def main():
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument('--anio', type=int, default=None)
    analizador.add_argument('--reemplazar', action='store_true')
    analizador.add_argument('--simular', action='store_true')
    argumentos = analizador.parse_args()

    df = leer_consolidados(anio=argumentos.anio)
    if df.empty:
        print('No hay filas para importar.')
        return 1

    _resumen_mapeo(df)
    filas = transformar(df)
    if argumentos.simular:
        print('\nSimulación: no se escribió nada en la base.')
        print(f'   Primera fila: {filas[0][:9]}')
        return 0

    conexion = conectar()
    try:
        cargar(conexion, filas, argumentos.reemplazar)
        verificar(conexion)
    except Exception as error:
        conexion.rollback()
        print(f'\nImportación fallida, se revirtió la transacción: {error}')
        return 1
    finally:
        conexion.close()

    print('\nConsolidados migrados. Ya puede ejecutarse etl_script.py.')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    sys.exit(main())
