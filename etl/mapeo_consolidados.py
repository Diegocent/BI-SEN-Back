# -*- coding: utf-8 -*-
"""Unifica los consolidados anuales 2018–2024 al contrato de la ingesta.

Cada planilla tiene encabezados, hojas y forma de anotar los kits distintos.
Este módulo las lee, descarta PII y hojas que no son asistencia por kits, y
devuelve un DataFrame con los nombres que espera `cargar_consolidados_a_ingesta`.

Una fila de consolidado = un titular asistido = una familia.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

ETL = Path(__file__).resolve().parent

# El formulario usa rural/urbano. Estas planillas traen indígena / no indígena.
# No se mezclan.
SEXO_MASCULINO = {'1'}
SEXO_FEMENINO = {'6'}

ANIO_MINIMO = 2018
ANIO_MAXIMO = 2026

SIN_ESPECIFICAR = 'SIN ESPECIFICAR'

TIPOS_KIT_B = {'B', 'TIPO B', 'KIT B', 'KIT TIPO B', 'TIPIO B'}
TIPOS_KIT_A = {
    'A', 'TIPO A', 'KIT A', 'KIT TIPO A', 'TIOP A',
    'NANGAREKO', 'NANGARECO', 'DONACION', 'ITAIPU', 'KIT ITAIPU',
    'KIT ITAIPIU', 'CORTE', 'PNUD', 'KIT ITAIPU',
}


def _norm(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ''
    texto = unicodedata.normalize('NFKD', str(valor))
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.upper().replace('\n', ' ')
    return re.sub(r'\s+', ' ', texto).strip()


def _entero(valor) -> int:
    numero = pd.to_numeric(valor, errors='coerce')
    if pd.isna(numero):
        return 0
    return max(0, int(round(float(numero))))


# Un titular recibe 1 kit, a veces unos pocos. Valores de 5-6 dígitos en
# 18-KIT ALIM / CantidadSubsidio son montos en guaraníes, no cantidades.
MAX_KITS_POR_TITULAR = 20
# Chapas y otros insumos por titular. 86.940 copiado a 78 filas es un total
# de comunidad, no techos individuales.
MAX_INSUMO_POR_TITULAR = 100


def _cantidad_kits(valor) -> int:
    cantidad = _entero(valor)
    if cantidad <= 0:
        return 0
    if cantidad > MAX_KITS_POR_TITULAR:
        return 1
    return cantidad


def _cantidad_insumo(valor) -> int:
    cantidad = _entero(valor)
    if cantidad <= 0:
        return 0
    return min(cantidad, MAX_INSUMO_POR_TITULAR)


def _sexo(valor):
    texto = _norm(valor)
    if texto.endswith('.0'):
        texto = texto[:-2]
    if not texto:
        return None
    if texto in SEXO_MASCULINO:
        return 'M'
    if texto in SEXO_FEMENINO:
        return 'F'
    return 'O'


def _indigena(valor):
    texto = _norm(valor)
    if not texto:
        return None
    compacto = texto.replace(' ', '')
    if compacto.startswith('NO') or texto.startswith('NO '):
        return False
    if any(marca in texto for marca in (
        'INDIG', 'IDIGENA', 'INDIEGAN', 'INDIGEMA', 'INIDGENA', 'COMUNIDAD',
    )):
        return True
    return None


def _fecha(serie: pd.Series) -> pd.Series:
    parseada = pd.to_datetime(serie, errors='coerce', dayfirst=True)
    serial = pd.to_numeric(serie, errors='coerce')
    desde_excel = pd.Timestamp('1899-12-30') + pd.to_timedelta(serial, unit='D')
    return parseada.fillna(desde_excel)


def _repartir_kits(fila: dict) -> tuple[int, int]:
    kit_alim = _cantidad_kits(fila.get('kit_alim'))
    cantidad = _cantidad_kits(fila.get('cantidad_subsidio'))
    limpieza = _cantidad_kits(fila.get('kit_limpieza'))
    tipo = _norm(fila.get('tipo_kit'))
    kit_a = 0
    kit_b = 0

    if kit_alim:
        if tipo in TIPOS_KIT_B:
            kit_b += kit_alim
        else:
            kit_a += kit_alim
    elif tipo in TIPOS_KIT_B:
        kit_b += cantidad or 1
    elif tipo in TIPOS_KIT_A:
        kit_a += cantidad or 1
    elif cantidad:
        kit_a += cantidad

    kit_b += limpieza
    return kit_a, kit_b


# Columnas de cada hoja útil. Los nombres son los del Excel, no los canónicos.
FUENTES = (
    {
        'archivo': 'CONSOLIDADO_2018.xlsx',
        'hoja': 'CONSOLIDADO',
        'anio': 2018,
        'cols': {
            'fecha': '7-fecha',
            'departamento': '4-Departamento',
            'distrito': '6-Distrito',
            'localidad': '8-Localidad',
            'evento': '2-Eventos',
            'sexo': '13-Sexo',
            'poblacion': '16-Tipo de Poblacion',
            'kit_alim': '18-Kit alim',
            'tipo_kit': '20-tipo de kit',
            'fibro': '21-Chapas Fibro',
            'zinc': '22-Chapas Zinc',
            'frazadas': '23-Frazadas',
            'colchones': '24-Colchón',
            'terciadas': '25-Madera Terciadas',
            'puntales': '26-Puntales',
            'carpas': '27-carpas Plast',
        },
    },
    {
        'archivo': 'consolidado_2019_formato_viejo.xlsx',
        'hoja': 'Hoja2',
        'anio': 2019,
        'cols': {
            'fecha': 'fecha',
            'departamento': 'Departamento',
            'distrito': 'Distrito',
            'localidad': 'Localidad',
            'evento': 'Eventos',
            'sexo': 'Sexo',
            'poblacion': 'Tipo de Poblacion',
            'kit_alim': 'Kit_alim',
            'fibro': 'Chapas Fibro',
            'zinc': 'Chapas Zinc',
            'frazadas': 'Frazadas',
            'colchones': 'Colchón',
            'terciadas': 'Madera Terciadas',
            'puntales': 'Puntales',
            'carpas': 'carpas Plast',
        },
    },
    {
        'archivo': 'CONSOLIDADO 2020 (1).xlsx',
        'hoja': 'ASISTENCIAS 2020',
        'anio': 2020,
        'cols': {
            'fecha': 'Fecha de aplicación del subsidio',
            'departamento': 'DEPARTAMENTO',
            'distrito': 'DISTRITO',
            'localidad': 'LOCALIDAD',
            'evento': 'EVENTO',
            'sexo': 'SEXO',
            'poblacion': 'TIPO DE POBLACION',
            'tipo_kit': 'TIPO DE KIT',
            'cantidad_subsidio': 'CantidadSubsidio',
            'fibro': 'CHAPA FIBRO',
            'zinc': 'CHAPA ZINC',
            'frazadas': 'FRAZADAS',
            'colchones': 'COLCHONES',
            'terciadas': 'MADERAS TERCIADAS',
            'puntales': 'PUNTALES',
            'carpas': 'CARPAS Plásticas',
        },
    },
    {
        'archivo': 'CONSOLIDADO 2020 (1).xlsx',
        'hoja': 'OLLA POPULAR ',
        'anio': 2020,
        'cols': {
            'fecha': 'Fecha de aplicación del subsidio',
            'departamento': 'DEPARTAMENTO',
            'distrito': 'DISTRITO',
            'localidad': 'LOCALIDAD',
            'evento': 'EVENTO',
            'sexo': 'SEXO',
            'poblacion': 'TIPO DE POBLACION',
            'tipo_kit': 'TIPO DE KIT',
            'cantidad_subsidio': 'CantidadSubsidio',
            'fibro': 'CHAPA FIBRO',
            'zinc': 'CHAPA ZINC',
            'frazadas': 'FRAZADAS',
            'colchones': 'COLCHONES',
            'terciadas': 'MADERAS TERCIADAS',
            'puntales': 'PUNTALES',
            'carpas': 'CARPAS Plásticas',
        },
    },
    {
        'archivo': 'CONSOLIDADO 2021.xlsx',
        'hoja': 'Hoja1',
        'anio': 2021,
        'cols': {
            'fecha': 'Fecha de aplicación del subsidio',
            'departamento': 'DEPARTAMENTO',
            'distrito': 'DISTRITO',
            'localidad': 'LOCALIDAD',
            'evento': 'EVENTO',
            'sexo': 'SEXO',
            'poblacion': 'TIPO DE POBLACION ',
            'tipo_kit': 'TIPO DE KIT',
            'cantidad_subsidio': 'CantidadSubsidio',
            'kit_limpieza': 'KITS DE LIMPIEZA',
            'fibro': 'CHAPA FIBRO',
            'zinc': 'CHAPA ZINC',
            'frazadas': 'FRAZADAS',
            'colchones': 'COLCHONES',
            'terciadas': 'MADERAS TERCIADAS',
            'puntales': 'PUNTALES',
            'carpas': 'CARPAS Plásticas',
        },
    },
    {
        'archivo': 'consolidado  2022.xlsx',
        'hoja': 'CONSOLIDADO 2022',
        'anio': 2022,
        'cols': {
            'fecha': '7-FECHA',
            'departamento': '4-DEPARTAMENTO',
            'distrito': '6-DISTRITO',
            'localidad': '8-LOCALIDAD',
            'evento': '2-EVENTOS',
            'sexo': '13-Sexo',
            'poblacion': '16-TIPO DE POBLACION',
            'kit_alim': '18-KIT ALIM',
            'tipo_kit': '20-TIPO DE KIT',
            'fibro': '21-CHAPAS FIBRO',
            'zinc': '22-CHAPAS ZINC',
            'frazadas': '23-FRAZADAS',
            'colchones': '24-COLCHÓN',
            'terciadas': '25-MADERA TERCIADAS',
            'puntales': '26-PUNTALES',
            'carpas': '27-CARPAS PLAST',
        },
    },
    {
        'archivo': 'CONSOLIDADO PARA CONTRALORIA 2023 U.V 1.xlsx',
        'hoja': 'CONSOLIDADO2023',
        'anio': 2023,
        'cols': {
            'fecha': '7-fecha',
            'departamento': '4-Departamento',
            'distrito': '6-Distrito',
            'localidad': '8-Localidad',
            'evento': '2-Eventos',
            'sexo': '13-Sexo',
            'poblacion': '16-Tipo de Poblacion',
            'kit_alim': '18-Kit alim',
            'tipo_kit': '20-tipo de kit',
            'fibro': '21-Chapas Fibro',
            'zinc': '22-Chapas Zinc',
            'frazadas': '23-Frazadas',
            'colchones': '24-Colchón',
            'terciadas': '25-Madera Terciadas',
            'puntales': '26-Puntales',
            'carpas': '27-carpas Plast',
        },
    },
    {
        'archivo': 'CONSOLIDADO-24.xlsx',
        'hoja': 'Hoja1',
        'anio': 2024,
        'cols': {
            'fecha': '7-fecha',
            'departamento': '4-Departamento',
            'distrito': '6-Distrito',
            'localidad': '8-Localidad',
            'evento': '2-Eventos',
            'sexo': '13-Sexo',
            'poblacion': '16-Tipo de Poblacion',
            'kit_alim': '18-Kit alim',
            'tipo_kit': '20-tipo de kit',
            'fibro': '21-Chapas Fibro',
            'zinc': '22-Chapas Zinc',
            'frazadas': '23-Frazadas',
            'colchones': '24-Colchón',
            'terciadas': '25-Madera Terciadas',
            'puntales': '26-Puntales',
            'carpas': '27-carpas Plast',
        },
    },
)


def _leer_fuente(fuente: dict, carpeta: Path) -> pd.DataFrame:
    camino = carpeta / fuente['archivo']
    if not camino.exists():
        raise FileNotFoundError(f'No se encontró {camino}')

    print(f'  Leyendo {camino.name} / {fuente["hoja"]!r}...')
    crudo = pd.read_excel(camino, sheet_name=fuente['hoja'], dtype=object)
    cols = fuente['cols']
    faltan = [origen for origen in cols.values() if origen not in crudo.columns]
    if faltan:
        raise KeyError(
            f'{camino.name} hoja {fuente["hoja"]!r} no tiene: {faltan}'
        )

    extraido = pd.DataFrame()
    for destino, origen in cols.items():
        extraido[destino] = crudo[origen]
    extraido['fuente_anio'] = fuente['anio']
    extraido['fuente_archivo'] = fuente['archivo']
    return extraido


def _estandarizar_con_cleaner(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica los diccionarios del DataCleaner sobre valores únicos."""
    from data_cleaner import DataCleaner

    cleaner = DataCleaner()
    df = df.copy()

    depto_map = {
        valor: cleaner.estandarizar_departamento_robusto(valor)
        for valor in df['DEPARTAMENTO'].unique()
    }
    df['DEPARTAMENTO'] = df['DEPARTAMENTO'].map(depto_map)

    evento_map = {
        valor: cleaner.estandarizar_evento_robusto(valor)
        for valor in df['EVENTO'].unique()
    }
    df['EVENTO'] = df['EVENTO'].map(evento_map)

    pares_distrito = df[['DISTRITO', 'DEPARTAMENTO']].drop_duplicates()
    dist_map = {}
    for distrito, departamento in pares_distrito.itertuples(index=False):
        dist_map[(distrito, departamento)] = cleaner.estandarizar_distrito_robusto(
            distrito, departamento,
        )
    df['DISTRITO'] = [
        dist_map.get((distrito, departamento), distrito)
        for distrito, departamento in zip(df['DISTRITO'], df['DEPARTAMENTO'])
    ]

    pares_loc = df[['LOCALIDAD', 'DISTRITO']].drop_duplicates()
    loc_map = {}
    for localidad, distrito in pares_loc.itertuples(index=False):
        loc_map[(localidad, distrito)] = cleaner.estandarizar_localidad_robusta(
            localidad, distrito,
        )
    df['LOCALIDAD'] = [
        loc_map.get((localidad, distrito), localidad) or SIN_ESPECIFICAR
        for localidad, distrito in zip(df['LOCALIDAD'], df['DISTRITO'])
    ]

    orden_map = {
        depto: int(cleaner.departamento_orden.get(depto, 0) or 0)
        for depto in df['DEPARTAMENTO'].unique()
    }
    df['ORDEN_DEPARTAMENTO'] = df['DEPARTAMENTO'].map(orden_map)
    return df


def leer_consolidados(carpeta: Path | None = None, anio: int | None = None) -> pd.DataFrame:
    """Lee y normaliza los consolidados. `anio` limita a una planilla."""
    carpeta = Path(carpeta) if carpeta else ETL
    fuentes = [
        fuente for fuente in FUENTES
        if anio is None or fuente['anio'] == anio
    ]
    if not fuentes:
        raise ValueError(f'No hay consolidado configurado para el año {anio}')

    print(f'\nUnificando {len(fuentes)} hoja(s) de consolidados...')
    bloques = [_leer_fuente(fuente, carpeta) for fuente in fuentes]
    crudo = pd.concat(bloques, ignore_index=True)
    print(f'  Filas crudas: {len(crudo):,}')

    fechas = _fecha(crudo['fecha'])
    kits = crudo.apply(_repartir_kits, axis=1, result_type='expand')
    kits.columns = ['kit_a', 'kit_b']

    canonico = pd.DataFrame({
        'FECHA': fechas,
        'DEPARTAMENTO': crudo['departamento'].map(_norm),
        'DISTRITO': crudo['distrito'].map(_norm),
        'LOCALIDAD': crudo['localidad'].map(_norm),
        'EVENTO': crudo['evento'].map(_norm),
        'SEXO': crudo['sexo'].map(_sexo),
        'ES_POBLACION_INDIGENA': crudo['poblacion'].map(_indigena),
        'KIT_A': kits['kit_a'],
        'KIT_B': kits['kit_b'],
        'CHAPA_FIBROCEMENTO': crudo['fibro'].map(_cantidad_insumo) if 'fibro' in crudo else 0,
        'CHAPA_ZINC': crudo['zinc'].map(_cantidad_insumo) if 'zinc' in crudo else 0,
        'COLCHONES': crudo['colchones'].map(_cantidad_insumo) if 'colchones' in crudo else 0,
        'FRAZADAS': crudo['frazadas'].map(_cantidad_insumo) if 'frazadas' in crudo else 0,
        'TERCIADAS': crudo['terciadas'].map(_cantidad_insumo) if 'terciadas' in crudo else 0,
        'PUNTALES': crudo['puntales'].map(_cantidad_insumo) if 'puntales' in crudo else 0,
        'CARPAS_PLASTICAS': crudo['carpas'].map(_cantidad_insumo) if 'carpas' in crudo else 0,
    })
    canonico['LOCALIDAD'] = canonico['LOCALIDAD'].replace('', SIN_ESPECIFICAR)
    canonico['DISTRITO'] = canonico['DISTRITO'].replace('', SIN_ESPECIFICAR)
    canonico['DEPARTAMENTO'] = canonico['DEPARTAMENTO'].replace('', SIN_ESPECIFICAR)

    insumos = (
        canonico['KIT_A'] + canonico['KIT_B']
        + canonico['CHAPA_FIBROCEMENTO'] + canonico['CHAPA_ZINC']
        + canonico['COLCHONES'] + canonico['FRAZADAS']
        + canonico['TERCIADAS'] + canonico['PUNTALES']
        + canonico['CARPAS_PLASTICAS']
    )
    fecha_ok = (
        canonico['FECHA'].notna()
        & (canonico['FECHA'].dt.year >= ANIO_MINIMO)
        & (canonico['FECHA'].dt.year <= ANIO_MAXIMO)
        & (canonico['FECHA'] <= pd.Timestamp.today())
    )
    n_fecha = int((~fecha_ok).sum())
    n_insumo = int(((insumos <= 0) & fecha_ok).sum())
    canonico = canonico.loc[fecha_ok & (insumos > 0)].copy()
    print(f'  Descartadas por fecha fuera de {ANIO_MINIMO}-{ANIO_MAXIMO}: {n_fecha:,}')
    print(f'  Descartadas sin insumos: {n_insumo:,}')

    print('  Estandarizando geografía y eventos (valores únicos)...')
    canonico = _estandarizar_con_cleaner(canonico)

    eliminar = canonico['EVENTO'] == 'ELIMINAR_REGISTRO'
    if eliminar.any():
        print(f'  Descartadas por preposicionamiento: {int(eliminar.sum()):,}')
        canonico = canonico.loc[~eliminar].copy()

    print(f'  Filas listas: {len(canonico):,}')
    return canonico.reset_index(drop=True)
