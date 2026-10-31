import os
from pathlib import Path

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cargar .env si python-dotenv está disponible. Buscamos en el proyecto
try:
    from dotenv import load_dotenv
    env_path = Path(BASE_DIR) / '.env'
    if not env_path.exists():
        # también mirar en la carpeta padre por si el .env está arriba
        env_path = Path(BASE_DIR).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"⚙️ Cargando variables de entorno desde: {env_path}")
except Exception:
    # Si python-dotenv no está instalado, seguiremos leyendo desde os.environ
    pass


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY: Prefer leer SECRET_KEY desde variables de entorno
SECRET_KEY = os.environ.get('SECRET_KEY', 'tu_clave_secreta_aqui')

# DEBUG desde ENV (string 'True'/'False'), por defecto True en dev
DEBUG = os.environ.get('DEBUG', 'True').lower() in ['1', 'true', 'yes']

# ALLOWED_HOSTS: leer desde la variable de entorno DJANGO_ALLOWED_HOSTS
_hosts = os.environ.get(
			'DJANGO_ALLOWED_HOSTS',  
			'161.35.53.140,127.0.0.1,sen.yvagacore.com,sen-api.yvagacore.com,192.168.100.236'
)
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(',') if h.strip()]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',  # <--- Agregado para CORS
    'rest_framework',
    'django_filters',
    'api', # Asegúrate de que tu aplicación 'api' esté aquí
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # <--- Agregado para CORS (debe ir arriba)
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
# --- Configuración de CORS ---
CORS_ALLOWED_ORIGINS = [
    "https://sen.yvagacore.com",
    "https://sen-api.yvagacore.com",
    "http://192.168.100.101",
    "http://192.168.100.101:3000",
    "http://192.168.100.101:5173",
    "http://161.35.53.140:3227",
    "http://161.35.53.140",
]

CSRF_TRUSTED_ORIGINS = [
    "https://sen.yvagacore.com",
    "https://sen-api.yvagacore.com",
]

# Permitir también credenciales (cookies, auth, etc.)
CORS_ALLOW_CREDENTIALS = True

if DEBUG:
    CORS_ALLOWED_ORIGINS += [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    CSRF_TRUSTED_ORIGINS += [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

# Si querés permitir headers personalizados:
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

ROOT_URLCONF = 'businessAnalitycsBack.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'businessAnalitycsBack.wsgi.application'


# --- CONFIGURACIÓN DE BASES DE DATOS (desde variables de entorno) ---
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME', os.environ.get('DB_DW_NAME', 'data_warehouse')),
        'USER': os.environ.get('DB_USER', os.environ.get('DB_DW_USER', 'neondb_owner')),
        'PASSWORD': os.environ.get('DB_PASSWORD', os.environ.get('DB_DW_PASS', 'npg_4jZsgShV0xAd')),
        'HOST': os.environ.get('DB_HOST', os.environ.get('DB_DW_HOST', 'ep-gentle-meadow-acqg6ndn-pooler.sa-east-1.aws.neon.tech')),
        'PORT': os.environ.get('DB_PORT', os.environ.get('DB_DW_PORT', '5432')),
    }
}

# Configure sslmode (honor explicit env var, else default to 'disable' for localhost)
db_host = os.environ.get('DB_HOST', os.environ.get('DB_DW_HOST', ''))
# allow either DB_DW_SSLMODE or DB_SSLMODE to be set
env_sslmode = os.environ.get('DB_DW_SSLMODE', os.environ.get('DB_SSLMODE'))
if env_sslmode:
    sslmode = env_sslmode
else:
    # If connecting to localhost, default to disable to avoid "server does not support SSL" errors
    if db_host in ('localhost', '127.0.0.1', '::1', ''):
        sslmode = 'disable'
    else:
        sslmode = 'require'

# Build OPTIONS only if needed; include channel_binding only when explicitly provided
db_options = {'sslmode': sslmode}
channel_binding = os.environ.get('DB_CHANNEL_BINDING')
if channel_binding:
    db_options['channel_binding'] = channel_binding

# Attach OPTIONS and CONN_MAX_AGE back to DATABASES['default']
DATABASES['default']['OPTIONS'] = db_options
DATABASES['default']['CONN_MAX_AGE'] = int(os.environ.get('DB_CONN_MAX_AGE', '60'))

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = 'es-py'

TIME_ZONE = 'America/Asuncion'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = '/static/'
