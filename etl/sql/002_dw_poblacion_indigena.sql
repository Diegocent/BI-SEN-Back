-- =============================================================================
-- 002_dw_poblacion_indigena.sql
--
-- Agrega las medidas de población indígena al hecho ya creado por 000.
-- Idempotente. Rural/urbano no se toca: es otro dato.
-- =============================================================================

BEGIN;

ALTER TABLE hechos_asistencia_humanitaria
    ADD COLUMN IF NOT EXISTS cantidad_indigena     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cantidad_no_indigena  INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_indigena IS
    'Familias con titular indígena.';
COMMENT ON COLUMN hechos_asistencia_humanitaria.cantidad_no_indigena IS
    'Familias con titular no indígena.';

COMMIT;
