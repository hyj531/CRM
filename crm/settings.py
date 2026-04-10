import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

def _load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Prefer .env.dev for local dev, then fill missing keys from .env.
_load_env_file(BASE_DIR / '.env.dev')
_load_env_file(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'core.apps.CoreConfig',
    'approval.apps.ApprovalConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
]
if not DEBUG:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
MIDDLEWARE += [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'crm.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'crm.wsgi.application'
ASGI_APPLICATION = 'crm.asgi.application'

DATABASE_URL = os.getenv('DATABASE_URL')

POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT')

if DATABASE_URL:
    DEFAULT_DATABASE_URL = DATABASE_URL
elif any([POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT]):
    DEFAULT_DATABASE_URL = (
        f"postgres://{POSTGRES_USER or 'crm'}:{POSTGRES_PASSWORD or ''}"
        f"@{POSTGRES_HOST or '127.0.0.1'}:{POSTGRES_PORT or '5432'}"
        f"/{POSTGRES_DB or 'crm'}"
    )
else:
    DEFAULT_DATABASE_URL = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"

DATABASES = {
    'default': dj_database_url.config(
        default=DEFAULT_DATABASE_URL,
        conn_max_age=600,
    )
}

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

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = os.getenv('DJANGO_TIME_ZONE', 'Asia/Shanghai')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'core.User'

if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ]
else:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
AUTHENTICATION_BACKENDS = [
    'core.auth_backends.DingTalkBackend',
    'django.contrib.auth.backends.ModelBackend',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.DefaultPagination',
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
}

DINGTALK = {
    'CLIENT_ID': os.getenv('DINGTALK_CLIENT_ID', ''),
    'CLIENT_SECRET': os.getenv('DINGTALK_CLIENT_SECRET', ''),
    'CORP_ID': os.getenv('DINGTALK_CORP_ID', ''),
    'TOKEN_URL': os.getenv('DINGTALK_TOKEN_URL', ''),
    'USERINFO_URL': os.getenv('DINGTALK_USERINFO_URL', ''),
    'ACCESS_TOKEN': os.getenv('DINGTALK_ACCESS_TOKEN', ''),
    'DEPT_LIST_URL': os.getenv('DINGTALK_DEPT_LIST_URL', ''),
    'DEPT_DETAIL_URL': os.getenv('DINGTALK_DEPT_DETAIL_URL', ''),
    'USER_LIST_URL': os.getenv('DINGTALK_USER_LIST_URL', ''),
    'WEBHOOK': os.getenv('DINGTALK_WEBHOOK', ''),
    'MOCK_USER_ID': os.getenv('DINGTALK_MOCK_USER_ID', ''),
    'SYNC_FILE': os.getenv('DINGTALK_SYNC_FILE', ''),
    'TODO_CREATE_URL': os.getenv('DINGTALK_TODO_CREATE_URL', ''),
    'TODO_COMPLETE_URL': os.getenv('DINGTALK_TODO_COMPLETE_URL', ''),
    'TODO_OPERATOR_UNION_ID': os.getenv('DINGTALK_TODO_OPERATOR_UNION_ID', ''),
    'OWN_OA_PROCESS_CODE': os.getenv('DINGTALK_OWN_OA_PROCESS_CODE', ''),
    'OWN_OA_CREATE_URL': os.getenv('DINGTALK_OWN_OA_CREATE_URL', ''),
    'OWN_OA_FORM_LABEL': os.getenv('DINGTALK_OWN_OA_FORM_LABEL', ''),
    'TODO_ENABLED': os.getenv('DINGTALK_TODO_ENABLED', '0'),
}

FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', 'http://127.0.0.1:5173/app')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
    },
}
