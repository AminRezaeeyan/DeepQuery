from pathlib import Path
from datetime import timedelta
from decouple import config # Recommended: pip install python-decouple

BASE_DIR = Path(__file__).resolve().parent.parent


def csv_list(value):
    """Split a comma-separated env value into a list, dropping empty entries."""
    return [item.strip() for item in value.split(',') if item.strip()]


# --- CORE SECURITY ---
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
# Off unless .env turns it on, so a deployment never runs in debug mode by accident.
DEBUG = config('DEBUG', default=False, cast=bool)
# Encrypts provider API keys in the database (Fernet key). Empty: derived from SECRET_KEY.
FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY', default='')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=csv_list)

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
    'evaluation',
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
    # Every endpoint needs a signed-in user unless it opts out explicitly.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        # Sign-in, sign-up and token refresh, per client IP.
        "auth": config("AUTH_THROTTLE_RATE", default="10/minute"),
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', 
    default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500",
    cast=csv_list
)

SPECTACULAR_SETTINGS = {
    "TITLE": "DeepQuery API",
    "DESCRIPTION": "API documentation for the backend",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}

# --- EXTERNAL SERVICES ---
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
# Web search via ddgs (no key). Backends are tried in order; drop ones blocked on your network.
WEB_SEARCH_BACKENDS = config("WEB_SEARCH_BACKENDS", default="duckduckgo,yahoo")
WEB_SEARCH_TIMEOUT = config("WEB_SEARCH_TIMEOUT", default=10, cast=int)

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_TRACK_STARTED, CELERY_TASK_TIME_LIMIT, CELERY_TASK_ACKS_LATE = True, 3600, True

ZARINPAL_MERCHANT_ID = config("ZARINPAL_MERCHANT_ID", default="")
ZARINPAL_ACCESS_TOKEN = config("ZARINPAL_ACCESS_TOKEN", default="")
ZARINPAL_SANDBOX = config("ZARINPAL_SANDBOX", default=True, cast=bool)
# Where the web client runs; ZarinPal returns users to <CLIENT_URL>/payment/result.
CLIENT_URL = config("CLIENT_URL", default="http://localhost:5173")

# --- LOGGING ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": config("LOG_LEVEL", default="INFO")},
    # The HTTP clients log every request at INFO; keep only their warnings.
    "loggers": {name: {"level": "WARNING"} for name in ("httpx", "httpcore", "openai", "anthropic")},
}

# --- RETRIEVAL ---
# Size of the passages documents are split into for search, in tokens.
RAG_CHUNK_TOKENS = config("RAG_CHUNK_TOKENS", default=400, cast=int)
RAG_CHUNK_OVERLAP_TOKENS = config("RAG_CHUNK_OVERLAP_TOKENS", default=60, cast=int)

# --- RESEARCH AGENT ---
# Tool-calling turns before the agent must answer with what it has.
AGENT_MAX_STEPS = config("AGENT_MAX_STEPS", default=10, cast=int)
# Check an answer that used tools against their results before sending it (one extra model turn).
AGENT_REVIEW = config("AGENT_REVIEW", default=True, cast=bool)

# --- CODE EXECUTION (the agent's run_python tool) ---
# "auto" uses bubblewrap when installed (isolated filesystem and network),
# otherwise a plain subprocess with limits; "off" disables the tool.
CODE_SANDBOX = config("CODE_SANDBOX", default="auto")
CODE_TIMEOUT = config("CODE_TIMEOUT", default=20, cast=int)  # seconds
CODE_MEMORY_MB = config("CODE_MEMORY_MB", default=1024, cast=int)

# --- UPLOADS ---
# Uploads are stored under server/ (chat_images/, user_documents/) and never
# served from a public URL: chat images go through /api/messages/<uuid>/image/.
MEDIA_ROOT = BASE_DIR
DOCUMENT_MAX_UPLOAD_BYTES = config("DOCUMENT_MAX_UPLOAD_MB", default=20, cast=int) * 1024 * 1024
CHAT_IMAGE_MAX_UPLOAD_BYTES = config("CHAT_IMAGE_MAX_UPLOAD_MB", default=10, cast=int) * 1024 * 1024

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
