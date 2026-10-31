-- =============================================================================
-- 000_esquema_estrella.sql
--
-- Esquema estrella para una base NUEVA (sen_dw_dev). No altera el warehouse
-- de producción.
--
-- Grano del hecho: una fila por fecha + ubicación + evento.
-- Las familias de la ingesta se compactan en medidas aditivas (familias,
-- mujeres, hombres, otro, rural, urbana, insumos).
--
-- Prerrequisito: `python manage.py migrate` ya creó ingesta_asistencia_humanitaria.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS dim_fecha (
    id_fecha     SERIAL PRIMARY KEY,
    fecha        DATE NOT NULL UNIQUE,
    anio         INTEGER NOT NULL,
    mes          INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    nombre_mes   TEXT NOT NULL,
    dia_del_mes  INTEGER NOT NULL CHECK (dia_del_mes BETWEEN 1 AND 31)
);

COMMENT ON TABLE dim_fecha IS
    'Dimensión temporal. Una fila por día con al menos una asistencia.';

CREATE TABLE IF NOT EXISTS dim_evento (
    id_evento  SERIAL PRIMARY KEY,
    evento     TEXT NOT NULL UNIQUE
);

COMMENT ON TABLE dim_evento IS
    'Catálogo de tipologías de evento ya normalizadas.';

CREATE TABLE IF NOT EXISTS dim_ubicacion (
    id_ubicacion   SERIAL PRIMARY KEY,
    departamento   TEXT NOT NULL,
    distrito       TEXT NOT NULL,
    localidad      TEXT NOT NULL,
    orden          INTEGER NOT NULL DEFAULT 0,
    UNIQUE (departamento, distrito, localidad)
);

COMMENT ON TABLE dim_ubicacion IS
    'Jerarquía geográfica. El orden es el de presentación oficial de departamentos.';

-- Una fila = el total de ese día, en ese lugar, para ese tipo de evento.
-- La clave única habilita el UPSERT del ETL: una carga tardía de la misma
-- fecha actualiza esta fila, no inserta otra.
CREATE TABLE IF NOT EXISTS hechos_asistencia_humanitaria (
    id_asistencia_hum            SERIAL PRIMARY KEY,
    id_fecha                     INTEGER NOT NULL
                                 REFERENCES dim_fecha (id_fecha),
    id_ubicacion                 INTEGER NOT NULL
                                 REFERENCES dim_ubicacion (id_ubicacion),
    id_evento                    INTEGER NOT NULL
                                 REFERENCES dim_evento (id_evento),
    kit_sentencia                INTEGER NOT NULL DEFAULT 0,
    kit_evento                   INTEGER NOT NULL DEFAULT 0,
    chapa_fibrocemento_cantidad  INTEGER NOT NULL DEFAULT 0,
    chapa_zinc_cantidad          INTEGER NOT NULL DEFAULT 0,
    colchones_cantidad           INTEGER NOT NULL DEFAULT 0,
    frazadas_cantidad            INTEGER NOT NULL DEFAULT 0,
    terciadas_cantidad           INTEGER NOT NULL DEFAULT 0,
    puntales_cantidad            INTEGER NOT NULL DEFAULT 0,
    carpas_plasticas_cantidad    INTEGER NOT NULL DEFAULT 0,
    cantidad_registros           INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_registros >= 0),
    cantidad_familias_asistidas  INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_familias_asistidas >= 0),
    cantidad_mujeres             INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_mujeres >= 0),
    cantidad_hombres             INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_hombres >= 0),
    cantidad_otro                INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_otro >= 0),
    cantidad_rural               INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_rural >= 0),
    cantidad_urbana              INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_urbana >= 0),
    cantidad_indigena            INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_indigena >= 0),
    cantidad_no_indigena         INTEGER NOT NULL DEFAULT 0
                                 CHECK (cantidad_no_indigena >= 0),
    UNIQUE (id_fecha, id_ubicacion, id_evento)
);

COMMENT ON TABLE hechos_asistencia_humanitaria IS
    'Hecho agregado. Una fila por fecha, ubicación y evento.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_registros IS
    'Filas de ingesta compactadas en esta clave (incluye el histórico de Excel).';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_familias_asistidas IS
    'Suma de familias. Cero en el histórico de Excel, que no relevó el dato.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_mujeres IS
    'Familias con titular femenino. Cero si el dato no se relevó.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_hombres IS
    'Familias con titular masculino. Cero si el dato no se relevó.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_otro IS
    'Familias con titular otro / no especificado.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_rural IS
    'Familias en zona rural.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_urbana IS
    'Familias en zona urbana.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_indigena IS
    'Familias con titular indígena. Cero si el dato no se relevó.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_no_indigena IS
    'Familias con titular no indígena.';

CREATE INDEX IF NOT EXISTS hechos_asis_hum_fecha_idx
    ON hechos_asistencia_humanitaria (id_fecha);

CREATE INDEX IF NOT EXISTS hechos_asis_hum_ubicacion_idx
    ON hechos_asistencia_humanitaria (id_ubicacion);

CREATE INDEX IF NOT EXISTS hechos_asis_hum_evento_idx
    ON hechos_asistencia_humanitaria (id_evento);

COMMIT;
