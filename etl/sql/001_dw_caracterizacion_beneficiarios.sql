-- =============================================================================
-- 001_dw_caracterizacion_beneficiarios.sql
--
-- SOLO para el Data Warehouse YA EXISTENTE si aún no se migró al grano
-- agregado. En sen_dw_dev y cualquier base nueva use 000_esquema_estrella.sql
-- (familias / mujeres / hombres / rural / urbana como medidas, sin sexo_titular
-- ni id_ingesta por fila).
--
-- Agrega a la tabla de hechos la caracterización de los beneficiarios que
-- aporta el nuevo sistema de ingesta:
--
--   * cantidad_familias_asistidas : medida aditiva.
--   * sexo_titular                : M / F / O.
--   * es_poblacion_rural          : verdadero = rural, falso = urbano.
--
-- Además incorpora `id_ingesta`, la referencia al registro transaccional de
-- origen. Esa columna cumple dos funciones: da trazabilidad auditable de cada
-- fila del hecho hasta el registro que la generó, y habilita una carga
-- idempotente por UPSERT que reemplaza al TRUNCATE del ETL anterior.
--
-- Las tres columnas de caracterización admiten NULL a propósito: los registros
-- históricos cargados desde la planilla Excel (2018-2023) no tienen ese dato y
-- no puede inferirse. NULL significa «no informado», y es preferible a un
-- valor por defecto que aparentaría un dato que nunca se relevó.
--
-- El script es idempotente: puede ejecutarse más de una vez sin efecto adverso.
--
-- Ejecución:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--        -f etl/sql/001_dw_caracterizacion_beneficiarios.sql
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Columnas nuevas
-- -----------------------------------------------------------------------------
ALTER TABLE hechos_asistencia_humanitaria
    ADD COLUMN IF NOT EXISTS cantidad_familias_asistidas INTEGER,
    ADD COLUMN IF NOT EXISTS sexo_titular                CHAR(1),
    ADD COLUMN IF NOT EXISTS es_poblacion_rural          BOOLEAN,
    ADD COLUMN IF NOT EXISTS id_ingesta                  BIGINT;

COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_familias_asistidas IS
    'Cantidad de familias asistidas. NULL en los registros históricos de Excel.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.sexo_titular IS
    'Sexo del titular del hogar: M, F u O. NULL en los registros históricos.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.es_poblacion_rural IS
    'Verdadero si la asistencia se entregó en zona rural. NULL si no se relevó.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.id_ingesta IS
    'Registro de ingesta_asistencia_humanitaria que originó esta fila.';

-- -----------------------------------------------------------------------------
-- 2. Reglas de integridad
--
-- PostgreSQL no admite ADD CONSTRAINT IF NOT EXISTS, así que se consulta el
-- catálogo antes de crear cada restricción para mantener la idempotencia.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hecho_sexo_titular_valido'
    ) THEN
        ALTER TABLE hechos_asistencia_humanitaria
            ADD CONSTRAINT hecho_sexo_titular_valido
            CHECK (sexo_titular IS NULL OR sexo_titular IN ('M', 'F', 'O'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hecho_familias_asistidas_minima'
    ) THEN
        ALTER TABLE hechos_asistencia_humanitaria
            ADD CONSTRAINT hecho_familias_asistidas_minima
            CHECK (cantidad_familias_asistidas IS NULL
                   OR cantidad_familias_asistidas >= 1);
    END IF;
END
$$;

-- Clave natural del hecho respecto del sistema transaccional. Es el soporte
-- del ON CONFLICT de la carga incremental.
--
-- El índice no es parcial a propósito: PostgreSQL admite múltiples NULL en un
-- índice único, así que las filas heredadas de la carga por Excel (con
-- id_ingesta nulo) conviven sin conflicto, y el ON CONFLICT del ETL no necesita
-- repetir un predicado para inferir el índice.
CREATE UNIQUE INDEX IF NOT EXISTS hechos_asis_hum_id_ingesta_uk
    ON hechos_asistencia_humanitaria (id_ingesta);

-- -----------------------------------------------------------------------------
-- 3. Índices para los filtros del tablero
--
-- Son índices parciales: excluyen los NULL del histórico, que representan la
-- mayor parte de las filas y nunca se filtran por estos campos.
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS hechos_asis_hum_sexo_titular_idx
    ON hechos_asistencia_humanitaria (sexo_titular)
    WHERE sexo_titular IS NOT NULL;

CREATE INDEX IF NOT EXISTS hechos_asis_hum_poblacion_rural_idx
    ON hechos_asistencia_humanitaria (es_poblacion_rural)
    WHERE es_poblacion_rural IS NOT NULL;

COMMIT;

-- -----------------------------------------------------------------------------
-- Verificación posterior sugerida:
--
--   SELECT column_name, data_type, is_nullable
--     FROM information_schema.columns
--    WHERE table_name = 'hechos_asistencia_humanitaria'
--      AND column_name IN ('cantidad_familias_asistidas', 'sexo_titular',
--                          'es_poblacion_rural', 'id_ingesta');
--
--   SELECT count(*) AS total,
--          count(sexo_titular) AS con_sexo,
--          count(es_poblacion_rural) AS con_zona,
--          count(cantidad_familias_asistidas) AS con_familias
--     FROM hechos_asistencia_humanitaria;
-- -----------------------------------------------------------------------------
