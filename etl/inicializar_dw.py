# -*- coding: utf-8 -*-
"""Aplica el esquema estrella sobre la base configurada en DB_DW_*.

Equivalente a `python manage.py inicializar_dw` del proyecto de ingesta, para
cuando se inicializa el warehouse desde este repositorio.

    python etl/inicializar_dw.py
"""

import os
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    import psycopg as psycopg2

SQL = Path(__file__).resolve().parent / 'sql' / '000_esquema_estrella.sql'


def _enunciados(script: str):
    lineas = [
        linea for linea in script.splitlines()
        if not linea.lstrip().startswith('--')
    ]
    for parte in '\n'.join(lineas).split(';'):
        sentencia = parte.strip()
        if sentencia and sentencia.upper() not in ('BEGIN', 'COMMIT'):
            yield sentencia


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

    faltantes = [c for c in ('DB_DW_USER', 'DB_DW_PASS') if not os.environ.get(c)]
    if faltantes:
        raise SystemExit(
            f'🛑 Faltan variables de entorno: {", ".join(faltantes)}'
        )

    return psycopg2.connect(
        dbname=os.environ.get('DB_DW_NAME', 'sen_dw_dev'),
        user=os.environ['DB_DW_USER'],
        password=os.environ['DB_DW_PASS'],
        host=os.environ.get('DB_DW_HOST', 'localhost'),
        port=os.environ.get('DB_DW_PORT', '5434'),
        sslmode=os.environ.get('DB_DW_SSLMODE', 'disable'),
    )


def main():
    if not SQL.exists():
        raise SystemExit(f'🛑 No se encontró {SQL}')

    conexion = conectar()
    try:
        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                     WHERE table_name = 'ingesta_asistencia_humanitaria';
                    """
                )
                if cursor.fetchone() is None:
                    raise SystemExit(
                        '🛑 No existe ingesta_asistencia_humanitaria. '
                        'Desde ingesta_sen/backend ejecute: python manage.py migrate'
                    )

                for sentencia in _enunciados(SQL.read_text(encoding='utf-8')):
                    cursor.execute(sentencia)

                cursor.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                     WHERE table_schema = 'public'
                       AND table_name LIKE ANY (
                           ARRAY['dim_%', 'hechos_%', 'ingesta_%']
                       )
                     ORDER BY 1;
                    """
                )
                print('✅ Esquema estrella aplicado:')
                for (nombre,) in cursor.fetchall():
                    print(f'   - {nombre}')
    finally:
        conexion.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
