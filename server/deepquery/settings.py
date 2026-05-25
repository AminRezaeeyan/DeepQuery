import os
from pathlib import Path
from datetime import timedelta
from decouple import config # Recommended: pip install python-decouple

BASE_DIR = Path(__file__).resolve().parent.parent

# --- CORE SECURITY ---
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=lambda v: [s.strip() for s in v.split(',')])

# --- APP DEFINITION ---
INSTALLED_APPS = [
    'jazzmin',  # Must be before admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third Party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    
    # Local Apps
    'users',
    'ai_core',
    'chats',
    'documents',
    'subscriptions',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'deepquery.urls'
WSGI_APPLICATION = 'deepquery.wsgi.application'
AUTH_USER_MODEL = 'users.User'

# --- DATABASE ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='deepquery'),
        'USER': config('DB_USER', default='deepquery_user'),
        'PASSWORD': config('DB_PASSWORD', default='deepquery_dev'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# --- TEMPLATES & I18N ---
TEMPLATES = [{
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
}]

LANGUAGE_CODE, TIME_ZONE = 'en-us', 'UTC'
USE_I18N, USE_TZ = True, True
STATIC_URL = 'static/'

# --- API & AUTH ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', 
    default="http://localhost:3000,http://127.0.0.1:3000", 
    cast=lambda v: [s.strip() for s in v.split(',')]
)

SPECTACULAR_SETTINGS = {
    "TITLE": "DeepQuery API",
    "DESCRIPTION": "API documentation for the backend",
    "VERSION": "1.0.0",
}

# --- EXTERNAL SERVICES ---
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
SERPER_API_KEY = config("SERPER_API_KEY", default="")

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_TRACK_STARTED, CELERY_TASK_TIME_LIMIT, CELERY_TASK_ACKS_LATE = True, 3600, True

ZARINPAL_MERCHANT_ID = config("ZARINPAL_MERCHANT_ID", default="")
ZARINPAL_ACCESS_TOKEN = config("ZARINPAL_ACCESS_TOKEN", default="")
ZARINPAL_SANDBOX = config("ZARINPAL_SANDBOX", default=True, cast=bool)

# --- UI CUSTOMIZATION ---
JAZZMIN_SETTINGS = {
    "site_title": "DeepQuery Admin",
    "site_header": "DeepQuery",
    "site_brand": "DeepQuery",
    "theme": "dark",
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_fixed": True,
    "sidebar_fixed": True,
    "theme": "default",
    "dark_mode_theme": "dark",
    "button_classes": {
        "primary": "btn-primary", "secondary": "btn-secondary",
        "info": "btn-info", "warning": "btn-warning",
        "danger": "btn-danger", "success": "btn-success"
    }
}
