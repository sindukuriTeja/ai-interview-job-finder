import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "database.db")}'
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    RECORDINGS_FOLDER = os.path.join(BASE_DIR, 'recordings')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max upload
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}
    ALLOWED_SEARCH_EXTENSIONS = {'pdf', 'docx', 'txt'}
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.2')
    QUESTIONS_PER_INTERVIEW = 10

    # Security settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Rate limiting
    RATE_LIMIT_UPLOAD = 5  # max uploads per minute
    RATE_LIMIT_SUBMIT = 30  # max answer submissions per minute
    RATE_LIMIT_GENERAL = 60  # max general requests per minute

    # Admin credentials (override via environment)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme123!')

    # Email notifications (optional)
    SMTP_SERVER = os.environ.get('SMTP_SERVER', '')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL', '')

    # Interview settings
    MAX_ANSWER_LENGTH = 5000
    QUESTION_TIME_LIMIT = 300  # 5 minutes per question
    MAX_VIOLATIONS_BEFORE_TERMINATE = 10
    # If an interview is in_progress but older than this (seconds), treat it as stale
    INTERVIEW_STALE_SECONDS = 6 * 3600


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True
