import time
import hashlib
import hmac
import re
from functools import wraps
from collections import defaultdict
from flask import request, jsonify, session, abort
from markupsafe import escape
from config import Config


class RateLimiter:
    def __init__(self):
        self._requests = defaultdict(list)

    def _cleanup(self, key, window):
        now = time.time()
        self._requests[key] = [t for t in self._requests[key] if now - t < window]

    def is_limited(self, key, max_requests, window=60):
        self._cleanup(key, window)
        if len(self._requests[key]) >= max_requests:
            return True
        self._requests[key].append(time.time())
        return False


rate_limiter = RateLimiter()


def rate_limit(max_requests, window=60, key_func=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if key_func:
                key = key_func()
            else:
                key = f"{f.__name__}:{get_client_ip()}"

            if rate_limiter.is_limited(key, max_requests, window):
                return jsonify({
                    'error': 'Too many requests. Please try again later.'
                }), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def sanitize_input(text, max_length=None):
    if text is None:
        return ''
    text = str(text).strip()
    if max_length:
        text = text[:max_length]
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    return text


def sanitize_html(text):
    if text is None:
        return ''
    return str(escape(text))


def validate_interview_access(interview_id, db, Interview):
    interview = db.query(Interview).get(interview_id)
    if not interview:
        return None, jsonify({'error': 'Interview not found'}), 404
    if interview.status == 'terminated':
        return None, jsonify({'error': 'This interview has been terminated'}), 403
    return interview, None, None


def hash_password(password):
    salt = hashlib.sha256(Config.SECRET_KEY.encode()).hexdigest()[:16]
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        100000
    ).hex()


def verify_password(password, password_hash):
    return hmac.compare_digest(hash_password(password), password_hash)


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return wrapped


def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=(self), geolocation=()'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return response


def validate_file_content(file_path):
    import magic
    try:
        mime = magic.from_file(file_path, mime=True)
        allowed_mimes = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        return mime in allowed_mimes
    except Exception:
        ext = file_path.rsplit('.', 1)[-1].lower()
        return ext in {'pdf', 'docx'}
