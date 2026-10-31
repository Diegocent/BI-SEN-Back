# -*- coding: utf-8 -*-
"""ETL del Data Warehouse de asistencia humanitaria.

Fuente: `ingesta_asistencia_humanitaria` (un registro = una familia, o una
fila histórica de Excel). Destino: esquema estrella.

El hecho no copia la ingesta 1 a 1. Compacta por
fecha + departamento + distrito + localidad + evento y guarda medidas
aditivas (insumos, familias, mujeres, hombres, otro, rural, urbana).

Cada corrida relee la ingesta y hace UPSERT sobre esa clave. Una carga
tardía de la misma fecha actualiza el total; no inserta una fila extra.

El formulario no necesita este script: un trigger en Postgres actualiza el
hecho al guardar. Instalarlo una vez:

    python etl/etl_script.py --instalar-refresco

    python etl/etl_script.py
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
except ImportError:
    import psycopg as psycopg2

TABLA_INGESTA = 'ingesta_asistencia_humanitaria'


CARGA_DIM_FECHA = f"""
    INSERT INTO dim_fecha (fecha, anio, mes, nombre_mes, dia_del_mes)
    SELECT DISTINCT
           i.fecha,
           i.anio,
           i.mes,
           i.nombre_mes,
           EXTRACT(DAY FROM i.fecha)::int
      FROM {TABLA_INGESTA} i
    ON CONFLICT (fecha) DO NOTHING;
"""

CARGA_DIM_EVENTO = f"""
    INSERT INTO dim_evento (evento)
    SELECT DISTINCT i.evento
      FROM {TABLA_INGESTA} i
    ON CONFLICT (evento) DO NOTHING;
"""

CARGA_DIM_UBICACION = f"""
    INSERT INTO dim_ubicacion (departamento, distrito, localidad, orden)
    SELECT DISTINCT
           i.departamento,
           i.distrito,
           i.localidad,
           i.orden_departamento
      FROM {TABLA_INGESTA} i
    ON CONFLICT (departamento, distrito, localidad)
    DO UPDATE SET orden = EXCLUDED.orden
     WHERE dim_ubicacion.orden IS DISTINCT FROM EXCLUDED.orden;
"""

CARGA_HECHOS = f"""
    INSERT INTO hechos_asistencia_humanitaria (
        id_fecha, id_ubicacion, id_evento,
        kit_sentencia, kit_evento,
        chapa_fibrocemento_cantidad, chapa_zinc_cantidad,
        colchones_cantidad, frazadas_cantidad, terciadas_cantidad,
        puntales_cantidad, carpas_plasticas_cantidad,
        cantidad_registros, cantidad_familias_asistidas,
        cantidad_mujeres, cantidad_hombres, cantidad_otro,
        cantidad_rural, cantidad_urbana,
        cantidad_indigena, cantidad_no_indigena
    )
    SELECT f.id_fecha,
           u.id_ubicacion,
           e.id_evento,
           COALESCE(SUM(i.kit_sentencia), 0),
           COALESCE(SUM(i.kit_evento), 0),
           COALESCE(SUM(i.chapa_fibrocemento), 0),
           COALESCE(SUM(i.chapa_zinc), 0),
           COALESCE(SUM(i.colchones), 0),
           COALESCE(SUM(i.frazadas), 0),
           COALESCE(SUM(i.terciadas), 0),
           COALESCE(SUM(i.puntales), 0),
           COALESCE(SUM(i.carpas_plasticas), 0),
           COUNT(*)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas), 0)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas) FILTER (
               WHERE i.sexo_titular = 'F'), 0)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas) FILTER (
               WHERE i.sexo_titular = 'M'), 0)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas) FILTER (
               WHERE i.sexo_titular = 'O'), 0)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas) FILTER (
               WHERE i.es_poblacion_rural IS TRUE), 0)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas) FILTER (
               WHERE i.es_poblacion_rural IS FALSE), 0)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas) FILTER (
               WHERE i.es_poblacion_indigena IS TRUE), 0)::int,
           COALESCE(SUM(i.cantidad_familias_asistidas) FILTER (
               WHERE i.es_poblacion_indigena IS FALSE), 0)::int
      FROM {TABLA_INGESTA} i
      JOIN dim_fecha  f ON f.fecha  = i.fecha
      JOIN dim_evento e ON e.evento = i.evento
      JOIN dim_ubicacion u
        ON u.departamento = i.departamento
       AND u.distrito     = i.distrito
       AND u.localidad    = i.localidad
     GROUP BY f.id_fecha, u.id_ubicacion, e.id_evento
    ON CONFLICT (id_fecha, id_ubicacion, id_evento) DO UPDATE SET
        kit_sentencia               = EXCLUDED.kit_sentencia,
        kit_evento                  = EXCLUDED.kit_evento,
        chapa_fibrocemento_cantidad = EXCLUDED.chapa_fibrocemento_cantidad,
        chapa_zinc_cantidad         = EXCLUDED.chapa_zinc_cantidad,
        colchones_cantidad          = EXCLUDED.colchones_cantidad,
        frazadas_cantidad           = EXCLUDED.frazadas_cantidad,
        terciadas_cantidad          = EXCLUDED.terciadas_cantidad,
        puntales_cantidad           = EXCLUDED.puntales_cantidad,
        carpas_plasticas_cantidad   = EXCLUDED.carpas_plasticas_cantidad,
        cantidad_registros          = EXCLUDED.cantidad_registros,
        cantidad_familias_asistidas = EXCLUDED.cantidad_familias_asistidas,
        cantidad_mujeres            = EXCLUDED.cantidad_mujeres,
        cantidad_hombres            = EXCLUDED.cantidad_hombres,
        cantidad_otro               = EXCLUDED.cantidad_otro,
        cantidad_rural              = EXCLUDED.cantidad_rural,
        cantidad_urbana             = EXCLUDED.cantidad_urbana,
        cantidad_indigena           = EXCLUDED.cantidad_indigena,
        cantidad_no_indigena        = EXCLUDED.cantidad_no_indigena;
"""

ELIMINAR_HUERFANOS = f"""
    DELETE FROM hechos_asistencia_humanitaria h
     WHERE NOT EXISTS (
           SELECT 1
             FROM {TABLA_INGESTA} i
             JOIN dim_fecha f ON f.fecha = i.fecha
             JOIN dim_evento e ON e.evento = i.evento
             JOIN dim_ubicacion u
               ON u.departamento = i.departamento
              AND u.distrito     = i.distrito
              AND u.localidad    = i.localidad
            WHERE h.id_fecha     = f.id_fecha
              AND h.id_ubicacion = u.id_ubicacion
              AND h.id_evento    = e.id_evento
       );
"""

DIAGNOSTICO_SIN_CARGAR = f"""
    SELECT i.departamento, i.distrito, i.localidad, i.evento, i.fecha, count(*)
      FROM {TABLA_INGESTA} i
      LEFT JOIN dim_fecha f ON f.fecha = i.fecha
      LEFT JOIN dim_evento e ON e.evento = i.evento
      LEFT JOIN dim_ubicacion u
        ON u.departamento = i.departamento
       AND u.distrito     = i.distrito
       AND u.localidad    = i.localidad
     WHERE f.id_fecha IS NULL
        OR e.id_evento IS NULL
        OR u.id_ubicacion IS NULL
     GROUP BY 1, 2, 3, 4, 5
     ORDER BY count(*) DESC
     LIMIT 20;
"""

RESUMEN = """
    SELECT count(*) AS filas_hecho,
           COALESCE(SUM(cantidad_registros), 0),
           COALESCE(SUM(cantidad_familias_asistidas), 0),
           COALESCE(SUM(cantidad_mujeres), 0),
           COALESCE(SUM(cantidad_hombres), 0),
           COALESCE(SUM(cantidad_otro), 0),
           COALESCE(SUM(cantidad_rural), 0),
           COALESCE(SUM(cantidad_urbana), 0),
           COALESCE(SUM(cantidad_indigena), 0),
           COALESCE(SUM(cantidad_no_indigena), 0)
      FROM hechos_asistencia_humanitaria;
"""

COLUMNAS_HECHO = (
    'cantidad_registros', 'cantidad_familias_asistidas',
    'cantidad_mujeres', 'cantidad_hombres', 'cantidad_otro',
    'cantidad_rural', 'cantidad_urbana',
    'cantidad_indigena', 'cantidad_no_indigena',
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
                print(f'⚙️ Variables de entorno cargadas desde {candidato}')
                break
    except ImportError:
        pass

    faltantes = [c for c in ('DB_DW_USER', 'DB_DW_PASS') if not os.environ.get(c)]
    if faltantes:
        raise SystemExit(
            f'🛑 Faltan variables de entorno obligatorias: {", ".join(faltantes)}'
        )

    host = os.environ.get('DB_DW_HOST', 'localhost')
    sslmode = os.environ.get('DB_DW_SSLMODE')
    if not sslmode:
        sslmode = 'disable' if host in ('localhost', '127.0.0.1', '::1') else 'require'

    conexion = psycopg2.connect(
        dbname=os.environ.get('DB_DW_NAME', 'sen_dw_dev'),
        user=os.environ['DB_DW_USER'],
        password=os.environ['DB_DW_PASS'],
        host=host,
        port=os.environ.get('DB_DW_PORT', '5434'),
        sslmode=sslmode,
    )
    print('✅ Conexión al Data Warehouse establecida.')
    return conexion


def verificar_prerrequisitos(cursor):
    cursor.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'hechos_asistencia_humanitaria'
           AND column_name = ANY(%s);
        """,
        (list(COLUMNAS_HECHO),),
    )
    presentes = {fila[0] for fila in cursor.fetchall()}
    faltan = set(COLUMNAS_HECHO) - presentes
    if faltan:
        raise SystemExit(
            '🛑 La tabla de hechos no tiene el grano agregado. '
            f'Faltan: {", ".join(sorted(faltan))}. '
            'En una base nueva ejecute: python manage.py inicializar_dw'
        )

    cursor.execute(f'SELECT count(*) FROM {TABLA_INGESTA};')
    total = cursor.fetchone()[0]
    print(f'📥 Registros disponibles en la ingesta: {total:,}')
    return total


def ejecutar(conexion):
    inicio = datetime.now()

    with conexion.cursor() as cursor:
        total_ingesta = verificar_prerrequisitos(cursor)

        print('\n⏳ Cargando dimensiones...')
        for nombre, sentencia in (
            ('dim_fecha', CARGA_DIM_FECHA),
            ('dim_evento', CARGA_DIM_EVENTO),
            ('dim_ubicacion', CARGA_DIM_UBICACION),
        ):
            cursor.execute(sentencia)
            print(f'  ✅ {nombre}: {cursor.rowcount:,} filas afectadas.')

        print('\n⏳ Compactando la ingesta en la tabla de hechos...')
        cursor.execute(CARGA_HECHOS)
        print(f'  ✅ hechos_asistencia_humanitaria: {cursor.rowcount:,} '
              'filas insertadas o actualizadas.')

        cursor.execute(ELIMINAR_HUERFANOS)
        if cursor.rowcount:
            print(f'  🧹 Hechos huérfanos eliminados: {cursor.rowcount:,}')

        cursor.execute(DIAGNOSTICO_SIN_CARGAR)
        sin_cargar = cursor.fetchall()
        if sin_cargar:
            print('\n⚠️ Registros de ingesta sin clave dimensional:')
            for departamento, distrito, localidad, evento, fecha, cantidad in sin_cargar:
                print(f'    {fecha} | {departamento} / {distrito} / {localidad} '
                      f'| {evento} -> {cantidad}')

        cursor.execute(RESUMEN)
        (filas, registros, familias, mujeres, hombres,
         otro, rural, urbana, indigena, no_indigena) = cursor.fetchone()

    conexion.commit()

    print('\n📊 Estado del Data Warehouse:')
    print(f'  Filas en el hecho (claves):     {filas:,}')
    print(f'  Registros de ingesta compactados: {registros:,}')
    print(f'  Familias asistidas:             {familias:,}')
    print(f'  Mujeres / hombres / otro:       {mujeres:,} / {hombres:,} / {otro:,}')
    print(f'  Rural / urbana:                 {rural:,} / {urbana:,}')
    print(f'  Indígena / no indígena:         {indigena:,} / {no_indigena:,}')
    print(f'  Filas en la ingesta:            {total_ingesta:,}')
    print(f'\n⏱️ Duración: {(datetime.now() - inicio).total_seconds():.1f} s')

    if registros != total_ingesta:
        print('\n⚠️ La suma de cantidad_registros no coincide con la ingesta.')


def main():
    analizador = argparse.ArgumentParser(
        description='Compacta la ingesta en el esquema estrella.'
    )
    analizador.add_argument(
        '--instalar-refresco',
        action='store_true',
        help='Instala el trigger que actualiza el BI al guardar en la ingesta.',
    )
    argumentos = analizador.parse_args()
    conexion = conectar()
    try:
        if argumentos.instalar_refresco:
            from refresco_dw import instalar
            instalar(conexion)
        ejecutar(conexion)
        print('\nETL completado. Los datos están disponibles para el tablero.')
        return 0
    except SystemExit:
        raise
    except Exception as error:
        conexion.rollback()
        print(f'\nETL fallido, se revirtió la transacción: {error}')
        return 1
    finally:
        conexion.close()


if __name__ == '__main__':
    sys.exit(main())
