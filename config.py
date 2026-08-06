import os
from datetime import timedelta
from dotenv import load_dotenv

# Automatically load environment variables from .env.development if available locally
if os.path.exists('.env.development'):
    load_dotenv('.env.development', override=True)
elif os.path.exists('.env'):
    load_dotenv('.env', override=True)

class BaseConfig:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'bcwa_portal_enterprise_security_key_2026')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    
    SUPABASE_URL = (os.environ.get('SUPABASE_URL') or '').strip().strip('"').strip("'")
    SUPABASE_ANON_KEY = (os.environ.get('SUPABASE_ANON_KEY') or '').strip().strip('"').strip("'")
    SUPABASE_SERVICE_KEY = (os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY') or '').strip().strip('"').strip("'")
    SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'documents')

class DevelopmentConfig(BaseConfig):
    ENV = 'development'
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    TEMPLATES_AUTO_RELOAD = True
    EXPLAIN_TEMPLATE_LOADING = False

class ProductionConfig(BaseConfig):
    ENV = 'production'
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    env = os.environ.get('FLASK_ENV') or os.environ.get('ENV')
    if not env:
        if os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'):
            env = 'production'
        else:
            env = 'development'
    return config_by_name.get(env.lower(), DevelopmentConfig)
