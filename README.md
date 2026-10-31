# Business Analytics Backend

Este proyecto es el backend de la plataforma de análisis de datos de ayudas, desarrollado con Django y Django REST Framework. Su objetivo es proveer una API robusta para la gestión, procesamiento y consulta de datos relacionados con eventos, ayudas y su distribución geográfica y temporal.

## Estructura del Proyecto

- **api/**: Aplicación principal del backend.
  - **models.py**: Definición de modelos de datos (tablas de la base de datos).
  - **serializers.py**: Serializadores para transformar modelos en JSON y viceversa.
  - **views.py**: Vistas y endpoints de la API (lógica de negocio y manejo de peticiones).
  - **urls.py**: Rutas de la API.
  - **admin.py**: Configuración del panel de administración de Django.
  - **tests.py**: Pruebas unitarias y de integración.
  - **migrations/**: Migraciones de la base de datos.
- **businessAnalitycsBack/**: Configuración global del proyecto Django.
  - **settings.py**: Configuración general (base de datos, apps instaladas, middlewares, etc.).
  - **urls.py**: Rutas principales del proyecto.
  - **asgi.py / wsgi.py**: Interfaces para servidores ASGI/WSGI.
- **etl/**: Scripts de ETL (Extracción, Transformación y Carga de datos).
  - **etl_script.py**: ETL recurrente. Lee la tabla `ingesta_asistencia_humanitaria` y carga las dimensiones y la tabla de hechos.
  - **cargar_historico_a_ingesta.py**: Migración única de la planilla histórica hacia la tabla de ingesta.
  - **data_cleaner.py**: Estandarización de los datos de la planilla. Solo lo usa la migración histórica.
  - **sql/**: Cambios de esquema del Data Warehouse, aplicables con `psql`.
- **manage.py**: Script de gestión de Django (migraciones, servidor, etc.).
- **requirements.txt**: Lista de dependencias del proyecto.
- **Dockerfile**: Contenerización del backend.
- **docker-compose.yml**: Orquestación de servicios (backend, base de datos, etc.).

## Principales Librerías Utilizadas

- **Django**: Framework principal para desarrollo web y API.
- **Django REST Framework**: Extensión para construir APIs RESTful.
- **Pandas**: Procesamiento y análisis de datos (usado en scripts ETL).
- **Otros**: Dependencias adicionales pueden incluir psycopg2 (PostgreSQL), numpy, etc. (ver `requirements.txt`).

## Funcionamiento General

El backend expone una API RESTful para que el frontend y otros clientes puedan consultar y manipular datos. La lógica principal se organiza en vistas (APIView y ViewSet) y endpoints, cada uno con filtros y serializadores específicos.

### Principales endpoints y su funcionamiento

Todos los endpoints aceptan parámetros de filtrado por fecha (`fecha_desde`, `fecha_hasta`), departamento, distrito, localidad, evento, año, mes, y otros según el caso. La paginación se controla con `per_page`.

- **/detallada/**: Devuelve el detalle de cada registro de ayuda, incluyendo ubicación, evento y cantidades. Permite filtros avanzados y paginación.
- **/anual/**: Devuelve totales de ayudas por año y tipo. Agrupa y suma los campos relevantes, excluyendo registros marcados como eliminados.
- **/mensual/**: Devuelve totales de ayudas por mes y tipo, agrupando por año y mes.
- **/por-ubicacion/**: Totales de ayudas agrupados por ubicación geográfica (departamento, distrito, localidad).
- **/por-departamento/**: Totales de ayudas agrupados por departamento, apilando los diferentes tipos de ayuda.
- **/por-evento/**: Totales de ayudas agrupados por tipo de evento.
- **/eventos-por-departamento/**: Número de eventos agrupados por departamento.
- **/eventos-por-localidad/**: Número de eventos agrupados por localidad.
- **/asistencias-por-anio-departamento/**: Totales de ayudas por año y departamento, útil para analizar la evolución temporal por región.
- **/tendencia-mensual-asistencias/**: Devuelve la tendencia mensual de asistencias, agrupando por año y mes.
- **/distribucion-mensual-detallada/**: Distribución detallada de ayudas por mes y tipo.
- **/distribucion-anual-producto/**: Evolución anual de un producto específico (filtrando por tipo de ayuda).
- **/asistencias-por-evento/**: Totales de ayudas distribuidas por tipo de evento.
- **/composicion-ayudas-por-evento/**: Composición de tipos de ayuda entregados por evento.
- **/ocurrencias-evento-anual/**: Número de ocurrencias de cada evento por año.
- **/incendios-anuales-por-departamento/**: Estadísticas de incendios por departamento y año.
- **/resumen-general/**: Resumen global de asistencias y eventos.
- **/resumen-por-departamento/**: Resumen de asistencias y eventos por departamento.

#### Ejemplo de lógica de un endpoint (`anual/`):

1. Se filtran los registros según los parámetros recibidos (fechas, departamento, etc.).
2. Se agrupa por año (`id_fecha__anio`).
3. Se anotan los totales de cada tipo de ayuda usando `Sum` y se calcula el total general.
4. Se serializa la respuesta y se pagina si corresponde.

#### Filtros avanzados

Se utilizan `django_filters` para permitir búsquedas complejas (por nombre de evento, localidad, cantidad de chapas, número de ocurrencias, etc.).

#### Respuesta de la API

Las respuestas suelen tener la forma:

```json
{
  "count": 100,
  "next": "...",
  "previous": null,
  "results": [
    { "anio": 2023, "kit_sentencia": 100, ... },
    ...
  ]
}
```

o bien un array simple si la paginación no aplica.

#### Seguridad y rendimiento

- Se utiliza paginación para evitar respuestas demasiado grandes.
- Los endpoints están optimizados con `select_related` y anotaciones para minimizar consultas a la base de datos.

### Relación con el frontend

Cada endpoint está diseñado para proveer exactamente los datos requeridos por los gráficos y tablas del frontend, permitiendo filtrado dinámico y agregaciones eficientes.

## Comandos y Scripts

- `python manage.py runserver`: Inicia el servidor de desarrollo.
- `python manage.py makemigrations`: Crea nuevas migraciones de base de datos.
- `python manage.py migrate`: Aplica migraciones.
- `python manage.py createsuperuser`: Crea un usuario administrador.
- `python etl/etl_script.py`: Compacta la ingesta en el Data Warehouse.
- `python etl/etl_script.py --instalar-refresco`: Instala el trigger que actualiza el BI al guardar una familia.
- `docker-compose up`: Levanta todos los servicios definidos en docker-compose.

## Configuración y Archivos Clave

- **settings.py**: Configuración de base de datos, apps, seguridad, etc.
- **requirements.txt**: Lista de dependencias Python.
- **Dockerfile / docker-compose.yml**: Para despliegue y orquestación.

## Notas Adicionales

- El backend está preparado para escalar y agregar nuevas entidades o endpoints.
- Se recomienda revisar los archivos de configuración y el `requirements.txt` para detalles de dependencias y configuraciones adicionales.

---

# Estructura de carpetas

```
businessAnalitycsBack/
├── api/
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── businessAnalitycsBack/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── etl/
│   ├── data_cleaner.py
│   └── etl_script.py
├── manage.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```
