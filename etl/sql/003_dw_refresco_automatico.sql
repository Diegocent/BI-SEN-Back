-- =============================================================================
-- 003_dw_refresco_automatico.sql
--
-- Cada INSERT/UPDATE/DELETE en la ingesta recalcula SOLO la clave afectada
-- del hecho (fecha + ubicación + evento). El tablero se actualiza al guardar
-- un formulario, sin correr el ETL completo.
--
-- Las cargas masivas de Excel deben pausar el trigger (lo hace el loader)
-- y luego correr etl_script.py una vez.
-- =============================================================================

CREATE OR REPLACE FUNCTION dw_refrescar_clave(
    p_fecha         date,
    p_departamento  text,
    p_distrito      text,
    p_localidad     text,
    p_evento        text
) RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
    v_id_fecha      integer;
    v_id_ubicacion  integer;
    v_id_evento     integer;
BEGIN
    IF p_fecha IS NULL
       OR p_departamento IS NULL
       OR p_distrito IS NULL
       OR p_localidad IS NULL
       OR p_evento IS NULL THEN
        RETURN;
    END IF;

    -- Una sola transacción a la vez por clave. Así dos cargas simultáneas
    -- del mismo operativo no se pisan el total: la segunda espera, vuelve a
    -- sumar y ve la fila de la primera.
    PERFORM pg_advisory_xact_lock(
        hashtext(concat_ws(E'\x1f', p_fecha::text, p_departamento, p_distrito)),
        hashtext(concat_ws(E'\x1f', p_localidad, p_evento))
    );

    INSERT INTO dim_fecha (fecha, anio, mes, nombre_mes, dia_del_mes)
    SELECT i.fecha, i.anio, i.mes, i.nombre_mes,
           EXTRACT(DAY FROM i.fecha)::int
      FROM ingesta_asistencia_humanitaria i
     WHERE i.fecha = p_fecha
     ORDER BY i.id
     LIMIT 1
    ON CONFLICT (fecha) DO NOTHING;

    INSERT INTO dim_evento (evento)
    VALUES (p_evento)
    ON CONFLICT (evento) DO NOTHING;

    INSERT INTO dim_ubicacion (departamento, distrito, localidad, orden)
    VALUES (
        p_departamento,
        p_distrito,
        p_localidad,
        COALESCE((
            SELECT MAX(i.orden_departamento)
              FROM ingesta_asistencia_humanitaria i
             WHERE i.departamento = p_departamento
               AND i.distrito     = p_distrito
               AND i.localidad    = p_localidad
        ), 0)
    )
    ON CONFLICT (departamento, distrito, localidad)
    DO UPDATE SET orden = EXCLUDED.orden
     WHERE dim_ubicacion.orden IS DISTINCT FROM EXCLUDED.orden;

    SELECT id_fecha INTO v_id_fecha
      FROM dim_fecha WHERE fecha = p_fecha;
    SELECT id_evento INTO v_id_evento
      FROM dim_evento WHERE evento = p_evento;
    SELECT id_ubicacion INTO v_id_ubicacion
      FROM dim_ubicacion
     WHERE departamento = p_departamento
       AND distrito     = p_distrito
       AND localidad    = p_localidad;

    IF v_id_fecha IS NULL OR v_id_evento IS NULL OR v_id_ubicacion IS NULL THEN
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM ingesta_asistencia_humanitaria i
         WHERE i.fecha         = p_fecha
           AND i.departamento  = p_departamento
           AND i.distrito      = p_distrito
           AND i.localidad     = p_localidad
           AND i.evento        = p_evento
    ) THEN
        DELETE FROM hechos_asistencia_humanitaria
         WHERE id_fecha     = v_id_fecha
           AND id_ubicacion = v_id_ubicacion
           AND id_evento    = v_id_evento;
        RETURN;
    END IF;

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
    SELECT v_id_fecha,
           v_id_ubicacion,
           v_id_evento,
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
      FROM ingesta_asistencia_humanitaria i
     WHERE i.fecha         = p_fecha
       AND i.departamento  = p_departamento
       AND i.distrito      = p_distrito
       AND i.localidad     = p_localidad
       AND i.evento        = p_evento
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
END;
$fn$;


CREATE OR REPLACE FUNCTION dw_trg_ingesta_refrescar() RETURNS trigger
LANGUAGE plpgsql
AS $tg$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM dw_refrescar_clave(
            NEW.fecha, NEW.departamento, NEW.distrito, NEW.localidad, NEW.evento
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        PERFORM dw_refrescar_clave(
            OLD.fecha, OLD.departamento, OLD.distrito, OLD.localidad, OLD.evento
        );
        IF (NEW.fecha, NEW.departamento, NEW.distrito, NEW.localidad, NEW.evento)
           IS DISTINCT FROM
           (OLD.fecha, OLD.departamento, OLD.distrito, OLD.localidad, OLD.evento)
        THEN
            PERFORM dw_refrescar_clave(
                NEW.fecha, NEW.departamento, NEW.distrito, NEW.localidad, NEW.evento
            );
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        PERFORM dw_refrescar_clave(
            OLD.fecha, OLD.departamento, OLD.distrito, OLD.localidad, OLD.evento
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$tg$;


DROP TRIGGER IF EXISTS trg_ingesta_refrescar_hechos
    ON ingesta_asistencia_humanitaria;

CREATE TRIGGER trg_ingesta_refrescar_hechos
AFTER INSERT OR UPDATE OR DELETE ON ingesta_asistencia_humanitaria
FOR EACH ROW
EXECUTE FUNCTION dw_trg_ingesta_refrescar();

COMMENT ON FUNCTION dw_refrescar_clave(date, text, text, text, text) IS
    'Recalcula el hecho de una clave. Serializa con pg_advisory_xact_lock para cargas concurrentes.';
COMMENT ON TRIGGER trg_ingesta_refrescar_hechos ON ingesta_asistencia_humanitaria IS
    'Mantiene el Data Warehouse al día cuando entra, se edita o se borra una familia.';
