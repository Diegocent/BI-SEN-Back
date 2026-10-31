# -*- coding: utf-8 -*-
"""Instala y pausa el refresco automático ingesta → hechos."""

from pathlib import Path

TRIGGER = 'trg_ingesta_refrescar_hechos'
SQL_REFRESCO = Path(__file__).resolve().parent / 'sql' / '003_dw_refresco_automatico.sql'


def _trigger_existe(cursor) -> bool:
    cursor.execute(
        """
        SELECT 1
          FROM pg_trigger t
          JOIN pg_class c ON c.oid = t.tgrelid
         WHERE t.tgname = %s
           AND c.relname = 'ingesta_asistencia_humanitaria'
           AND NOT t.tgisinternal;
        """,
        (TRIGGER,),
    )
    return cursor.fetchone() is not None


def instalar(conexion) -> None:
    sql = SQL_REFRESCO.read_text(encoding='utf-8')
    with conexion.cursor() as cursor:
        cursor.execute(sql)
    conexion.commit()
    print(f'Refresco automático instalado desde {SQL_REFRESCO.name}.')


def pausar(cursor, pausar_refresco: bool) -> None:
    """Las cargas masivas pausan el trigger para no recalcular fila por fila."""
    if not _trigger_existe(cursor):
        return
    accion = 'DISABLE' if pausar_refresco else 'ENABLE'
    cursor.execute(
        f'ALTER TABLE ingesta_asistencia_humanitaria {accion} TRIGGER {TRIGGER};'
    )
