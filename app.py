import os
import json
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from config import Config
from models import (
    init_db, Session as DBSession, Candidate, Interview,
    Question, Answer, ProctorLog, AuditLog, Admin
)
from services.resume_parser import parse_resume
from services.question_generator import generate_questions
from services.evaluator import evaluate_answer
from security import (
    rate_limit, sanitize_input, get_client_ip,
    add_security_headers, admin_required, hash_password,
    verify_password, validate_interview_access, RateLimiter
)
from job_search import register_job_search_routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('interview_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.RECORDINGS_FOLDER, exist_ok=True)

init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

register_job_search_routes(app, login_required)


@app.after_request
def apply_security_headers(response):
    return add_security_headers(response)


def log_audit(action, actor=None, target_type=None, target_id=None, details=None):
    db = DBSession()
    try:
        log = AuditLog(
            action=action,
            actor=actor or get_client_ip(),
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=get_client_ip()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Audit log failed: {e}")
    finally:
        db.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
@rate_limit(Config.RATE_LIMIT_UPLOAD)
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF and DOCX files are allowed'}), 400

    if file.content_length and file.content_length > Config.MAX_CONTENT_LENGTH:
        return jsonify({'error': 'File too large. Maximum 10MB allowed'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(file_path)

    file_size = os.path.getsize(file_path)
    if file_size > Config.MAX_CONTENT_LENGTH:
        os.remove(file_path)
        return jsonify({'error': 'File too large'}), 400

    if file_size == 0:
        os.remove(file_path)
        return jsonify({'error': 'Empty file uploaded'}), 400

    resume_data = parse_resume(file_path)
    if not resume_data:
        os.remove(file_path)
        return jsonify({'error': 'Failed to parse resume. Please ensure the file is valid.'}), 500

    db = DBSession()
    try:
        candidate = Candidate(
            name=sanitize_input(resume_data.get('name', 'Unknown'), 200),
            email=sanitize_input(resume_data.get('email', ''), 200),
            phone=sanitize_input(resume_data.get('phone', ''), 50),
            resume_path=file_path,
            skills=json.dumps(resume_data.get('skills', [])),
            experience_years=min(50, max(0, resume_data.get('experience_years', 0))),
            education=json.dumps(resume_data.get('education', [])),
            job_titles=json.dumps(resume_data.get('job_titles', [])),
            ip_address=get_client_ip(),
            user_agent=sanitize_input(request.headers.get('User-Agent', ''), 500)
        )
        db.add(candidate)
        db.commit()

        resume_data['candidate_id'] = candidate.id
        resume_data.pop('raw_text', None)

        log_audit('resume_upload', target_type='candidate', target_id=candidate.id)
        logger.info(f"Resume uploaded for candidate {candidate.id} from {get_client_ip()}")

        return jsonify({
            'success': True,
            'candidate_id': candidate.id,
            'resume_data': resume_data
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Upload error: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        db.close()


@app.route('/start-interview/<int:candidate_id>', methods=['POST'])
@rate_limit(10)
def start_interview(candidate_id):
    db = DBSession()
    try:
        candidate = db.query(Candidate).get(candidate_id)
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404

        in_prog = db.query(Interview).filter_by(
            candidate_id=candidate_id, status='in_progress'
        ).all()

        # Auto-terminate stale in-progress interviews older than configured threshold
        stale_threshold = getattr(Config, 'INTERVIEW_STALE_SECONDS', 6 * 3600)
        now = datetime.utcnow()
        non_stale = []
        if in_prog:
            for iv in in_prog:
                # If start_time is missing treat as non-stale to be safe
                if iv.start_time and (now - iv.start_time).total_seconds() > stale_threshold:
                    iv.status = 'terminated'
                    iv.is_flagged = True
                    iv.flag_reason = 'Auto-terminated: stale interview'
                else:
                    non_stale.append(iv)
            db.commit()

        if non_stale:
            return jsonify({'error': 'An interview is already in progress for this candidate'}), 409

        resume_data = {
            'name': candidate.name,
            'skills': json.loads(candidate.skills) if candidate.skills else [],
            'experience_years': candidate.experience_years,
            'education': json.loads(candidate.education) if candidate.education else [],
            'job_titles': json.loads(candidate.job_titles) if candidate.job_titles else []
        }

        questions = generate_questions(resume_data, Config.QUESTIONS_PER_INTERVIEW)

        interview = Interview(
            candidate_id=candidate_id,
            status='in_progress',
            total_questions=len(questions),
            start_time=datetime.utcnow(),
            browser_fingerprint=sanitize_input(request.headers.get('User-Agent', ''), 256)
        )
        db.add(interview)
        db.commit()

        db_questions = []
        for i, q in enumerate(questions):
            db_question = Question(
                interview_id=interview.id,
                question_text=q['question'],
                category=q.get('category', 'general'),
                difficulty=q.get('difficulty', 'medium'),
                skill_targeted=q.get('skill_targeted', 'general'),
                order_num=i + 1,
                source=q.get('source', 'rule_based')
            )
            db.add(db_question)
            db_questions.append(db_question)

        db.commit()

        questions_response = []
        for dbq in db_questions:
            questions_response.append({
                'id': dbq.id,
                'question': dbq.question_text,
                'category': dbq.category,
                'difficulty': dbq.difficulty,
                'skill_targeted': dbq.skill_targeted,
                'order': dbq.order_num
            })

        log_audit('interview_started', target_type='interview', target_id=interview.id)
        logger.info(f"Interview {interview.id} started for candidate {candidate_id}")

        return jsonify({
            'success': True,
            'interview_id': interview.id,
            'questions': questions_response,
            'candidate_name': candidate.name
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Start interview error: {e}")
        return jsonify({'error': 'Failed to start interview'}), 500
    finally:
        db.close()


@app.route('/interview/<int:interview_id>')
def interview_page(interview_id):
    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        if not interview:
            return redirect('/')
        if interview.status == 'completed':
            return redirect(f'/results/{interview_id}')
        if interview.status == 'terminated':
            return render_template('terminated.html')
    finally:
        db.close()
    return render_template('interview.html', interview_id=interview_id)


@app.route('/submit-answer', methods=['POST'])
@rate_limit(Config.RATE_LIMIT_SUBMIT)
def submit_answer():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    interview_id = data.get('interview_id')
    question_id = data.get('question_id')
    answer_text = sanitize_input(data.get('answer_text', ''), Config.MAX_ANSWER_LENGTH)
    time_taken = data.get('time_taken', 0)
    paste_detected = data.get('paste_detected', False)

    if not interview_id or not question_id:
        return jsonify({'error': 'Missing required fields'}), 400

    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        question = db.query(Question).get(question_id)

        if not interview or not question:
            return jsonify({'error': 'Interview or question not found'}), 404

        if interview.status != 'in_progress':
            return jsonify({'error': 'Interview is not active'}), 403

        if interview.proctoring_violations and interview.proctoring_violations >= Config.MAX_VIOLATIONS_BEFORE_TERMINATE:
            interview.status = 'terminated'
            interview.flag_reason = 'Exceeded maximum proctoring violations'
            interview.is_flagged = True
            db.commit()
            return jsonify({'error': 'Interview terminated due to violations', 'terminated': True}), 403

        existing = db.query(Answer).filter_by(
            interview_id=interview_id, question_id=question_id
        ).first()
        if existing:
            return jsonify({'error': 'Answer already submitted for this question'}), 409

        candidate = db.query(Candidate).get(interview.candidate_id)
        resume_data = {
            'skills': json.loads(candidate.skills) if candidate.skills else [],
            'experience_years': candidate.experience_years
        }

        scores = evaluate_answer(question.question_text, answer_text, resume_data)

        answer = Answer(
            interview_id=interview_id,
            question_id=question_id,
            answer_text=answer_text,
            relevance_score=scores['relevance'],
            completeness_score=scores['completeness'],
            accuracy_score=scores['accuracy'],
            communication_score=scores['communication'],
            overall_score=scores['overall'],
            feedback=scores['feedback'],
            time_taken_seconds=min(600, max(0, int(time_taken))) if time_taken else None,
            paste_detected=bool(paste_detected)
        )
        db.add(answer)

        if paste_detected:
            interview.is_flagged = True
            if not interview.flag_reason:
                interview.flag_reason = 'Copy-paste detected'

        db.commit()

        return jsonify({
            'success': True,
            'scores': scores
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Submit answer error: {e}")
        return jsonify({'error': 'Failed to evaluate answer'}), 500
    finally:
        db.close()


@app.route('/log-violation', methods=['POST'])
@rate_limit(60)
def log_violation():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    interview_id = data.get('interview_id')
    violation_type = sanitize_input(data.get('violation_type'), 100)
    description = sanitize_input(data.get('description', ''), 500)
    severity = data.get('severity', 'medium')

    if severity not in ('low', 'medium', 'high'):
        severity = 'medium'

    if not interview_id or not violation_type:
        return jsonify({'error': 'Missing required fields'}), 400

    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        if not interview or interview.status != 'in_progress':
            return jsonify({'error': 'Interview not found or inactive'}), 404

        log = ProctorLog(
            interview_id=interview_id,
            violation_type=violation_type,
            description=description,
            severity=severity
        )
        db.add(log)

        interview.proctoring_violations = (interview.proctoring_violations or 0) + 1

        terminated = False
        if interview.proctoring_violations >= Config.MAX_VIOLATIONS_BEFORE_TERMINATE:
            interview.status = 'terminated'
            interview.is_flagged = True
            interview.flag_reason = 'Auto-terminated: too many violations'
            terminated = True
            logger.warning(f"Interview {interview_id} auto-terminated due to violations")

        db.commit()
        return jsonify({'success': True, 'terminated': terminated})
    except Exception as e:
        db.rollback()
        logger.error(f"Log violation error: {e}")
        return jsonify({'error': 'Failed to log violation'}), 500
    finally:
        db.close()


@app.route('/complete-interview/<int:interview_id>', methods=['POST'])
@rate_limit(10)
def complete_interview(interview_id):
    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404

        if interview.status not in ('in_progress',):
            return jsonify({'error': 'Interview cannot be completed'}), 400

        interview.status = 'completed'
        interview.end_time = datetime.utcnow()

        answers = db.query(Answer).filter_by(interview_id=interview_id).all()
        if answers:
            total_score = sum(a.overall_score for a in answers) / len(answers)
            interview.total_score = round(total_score, 1)

        db.commit()

        log_audit('interview_completed', target_type='interview', target_id=interview_id,
                  details=f"Score: {interview.total_score}")
        logger.info(f"Interview {interview_id} completed with score {interview.total_score}")

        return jsonify({
            'success': True,
            'redirect': f'/results/{interview_id}'
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Complete interview error: {e}")
        return jsonify({'error': 'Failed to complete interview'}), 500
    finally:
        db.close()


@app.route('/results/<int:interview_id>')
def results_page(interview_id):
    return render_template('results.html', interview_id=interview_id)


@app.route('/api/results/<int:interview_id>')
@rate_limit(30)
def get_results(interview_id):
    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404

        candidate = db.query(Candidate).get(interview.candidate_id)
        answers = db.query(Answer).filter_by(interview_id=interview_id).all()
        violations = db.query(ProctorLog).filter_by(interview_id=interview_id).all()

        answers_data = []
        for answer in answers:
            question = db.query(Question).get(answer.question_id)
            answers_data.append({
                'question': question.question_text if question else '',
                'category': question.category if question else '',
                'difficulty': question.difficulty if question else '',
                'answer': answer.answer_text,
                'scores': {
                    'relevance': answer.relevance_score,
                    'completeness': answer.completeness_score,
                    'accuracy': answer.accuracy_score,
                    'communication': answer.communication_score,
                    'overall': answer.overall_score
                },
                'feedback': answer.feedback,
                'time_taken': answer.time_taken_seconds,
                'paste_detected': answer.paste_detected
            })

        violations_data = [{
            'type': v.violation_type,
            'description': v.description,
            'severity': v.severity,
            'timestamp': v.timestamp.isoformat() if v.timestamp else ''
        } for v in violations]

        duration = None
        if interview.start_time and interview.end_time:
            diff = interview.end_time - interview.start_time
            duration = int(diff.total_seconds())

        return jsonify({
            'candidate': {
                'name': candidate.name,
                'email': candidate.email,
                'skills': json.loads(candidate.skills) if candidate.skills else [],
                'experience_years': candidate.experience_years
            },
            'interview': {
                'id': interview.id,
                'total_score': interview.total_score,
                'total_questions': interview.total_questions,
                'answers_count': len(answers),
                'violations_count': interview.proctoring_violations,
                'duration': duration,
                'status': interview.status,
                'is_flagged': interview.is_flagged,
                'flag_reason': interview.flag_reason
            },
            'answers': answers_data,
            'violations': violations_data
        })
    finally:
        db.close()


# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
@rate_limit(5, window=300)
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html')

    data = request.json or request.form
    username = sanitize_input(data.get('username', ''), 100)
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        session['admin_username'] = username
        session.permanent = True
        log_audit('admin_login', actor=username)
        logger.info(f"Admin login: {username} from {get_client_ip()}")
        return jsonify({'success': True, 'redirect': '/admin/dashboard'})

    logger.warning(f"Failed admin login attempt from {get_client_ip()}")
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/admin/logout')
def admin_logout():
    log_audit('admin_logout', actor=session.get('admin_username'))
    session.clear()
    return redirect('/admin/login')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/admin/api/stats')
@admin_required
def admin_stats():
    db = DBSession()
    try:
        total_candidates = db.query(Candidate).count()
        total_interviews = db.query(Interview).count()
        completed_interviews = db.query(Interview).filter_by(status='completed').count()
        in_progress = db.query(Interview).filter_by(status='in_progress').count()
        flagged = db.query(Interview).filter_by(is_flagged=True).count()
        terminated = db.query(Interview).filter_by(status='terminated').count()

        recent_interviews = db.query(Interview).order_by(
            Interview.created_at.desc()
        ).limit(20).all()

        interviews_data = []
        for interview in recent_interviews:
            candidate = db.query(Candidate).get(interview.candidate_id)
            violations = db.query(ProctorLog).filter_by(interview_id=interview.id).count()
            interviews_data.append({
                'id': interview.id,
                'candidate_name': candidate.name if candidate else 'Unknown',
                'candidate_email': candidate.email if candidate else '',
                'status': interview.status,
                'score': interview.total_score,
                'violations': violations,
                'is_flagged': interview.is_flagged,
                'flag_reason': interview.flag_reason,
                'created_at': interview.created_at.isoformat() if interview.created_at else '',
                'duration': int((interview.end_time - interview.start_time).total_seconds())
                    if interview.start_time and interview.end_time else None
            })

        return jsonify({
            'stats': {
                'total_candidates': total_candidates,
                'total_interviews': total_interviews,
                'completed': completed_interviews,
                'in_progress': in_progress,
                'flagged': flagged,
                'terminated': terminated
            },
            'recent_interviews': interviews_data
        })
    finally:
        db.close()


@app.route('/admin/api/interview/<int:interview_id>')
@admin_required
def admin_interview_detail(interview_id):
    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        if not interview:
            return jsonify({'error': 'Not found'}), 404

        candidate = db.query(Candidate).get(interview.candidate_id)
        answers = db.query(Answer).filter_by(interview_id=interview_id).all()
        violations = db.query(ProctorLog).filter_by(interview_id=interview_id).all()

        return jsonify({
            'interview': {
                'id': interview.id,
                'status': interview.status,
                'score': interview.total_score,
                'is_flagged': interview.is_flagged,
                'flag_reason': interview.flag_reason,
                'violations_count': interview.proctoring_violations,
                'start_time': interview.start_time.isoformat() if interview.start_time else None,
                'end_time': interview.end_time.isoformat() if interview.end_time else None,
            },
            'candidate': {
                'name': candidate.name,
                'email': candidate.email,
                'phone': candidate.phone,
                'skills': json.loads(candidate.skills) if candidate.skills else [],
                'experience_years': candidate.experience_years,
                'ip_address': candidate.ip_address
            },
            'answers': [{
                'question': db.query(Question).get(a.question_id).question_text if db.query(Question).get(a.question_id) else '',
                'answer': a.answer_text,
                'overall_score': a.overall_score,
                'feedback': a.feedback,
                'paste_detected': a.paste_detected,
                'time_taken': a.time_taken_seconds
            } for a in answers],
            'violations': [{
                'type': v.violation_type,
                'description': v.description,
                'severity': v.severity,
                'timestamp': v.timestamp.isoformat() if v.timestamp else ''
            } for v in violations]
        })
    finally:
        db.close()


@app.route('/admin/api/flag/<int:interview_id>', methods=['POST'])
@admin_required
def admin_flag_interview(interview_id):
    data = request.json or {}
    reason = sanitize_input(data.get('reason', 'Flagged by admin'), 500)

    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        if not interview:
            return jsonify({'error': 'Not found'}), 404

        interview.is_flagged = not interview.is_flagged
        if interview.is_flagged:
            interview.flag_reason = reason
        else:
            interview.flag_reason = None

        db.commit()
        log_audit('interview_flagged' if interview.is_flagged else 'interview_unflagged',
                  actor=session.get('admin_username'),
                  target_type='interview', target_id=interview_id)

        return jsonify({'success': True, 'is_flagged': interview.is_flagged})
    finally:
        db.close()


@app.route('/admin/api/terminate/<int:interview_id>', methods=['POST'])
@admin_required
def admin_terminate_interview(interview_id):
    db = DBSession()
    try:
        interview = db.query(Interview).get(interview_id)
        if not interview:
            return jsonify({'error': 'Not found'}), 404

        if interview.status == 'in_progress':
            interview.status = 'terminated'
            interview.end_time = datetime.utcnow()
            interview.is_flagged = True
            interview.flag_reason = 'Terminated by admin'
            db.commit()
            log_audit('interview_terminated', actor=session.get('admin_username'),
                      target_type='interview', target_id=interview_id)

        return jsonify({'success': True})
    finally:
        db.close()


@app.route('/admin/api/audit-log')
@admin_required
def admin_audit_log():
    db = DBSession()
    try:
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
        return jsonify({
            'logs': [{
                'action': log.action,
                'actor': log.actor,
                'target_type': log.target_type,
                'target_id': log.target_id,
                'details': log.details,
                'ip_address': log.ip_address,
                'timestamp': log.timestamp.isoformat() if log.timestamp else ''
            } for log in logs]
        })
    finally:
        db.close()


# ==================== UTILITY ROUTES ====================

@app.route('/check-ollama')
@rate_limit(10)
def check_ollama():
    from services.ollama_client import OllamaClient
    client = OllamaClient()
    return jsonify({
        'available': client.is_available(),
        'model': Config.OLLAMA_MODEL
    })


@app.route('/health')
def health_check():
    from sqlalchemy import text
    db = DBSession()
    try:
        db.execute(text("SELECT 1"))
        db_status = True
    except Exception:
        db_status = False
    finally:
        db.close()

    return jsonify({
        'status': 'healthy' if db_status else 'degraded',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/history')
def interview_history():
    return render_template('history.html')


@app.route('/api/history')
@rate_limit(30)
def get_history():
    db = DBSession()
    try:
        interviews = db.query(Interview).filter(
            Interview.status.in_(['completed', 'terminated'])
        ).order_by(Interview.created_at.desc()).limit(50).all()

        results = []
        for interview in interviews:
            candidate = db.query(Candidate).get(interview.candidate_id)
            results.append({
                'id': interview.id,
                'candidate_name': candidate.name if candidate else 'Unknown',
                'status': interview.status,
                'score': interview.total_score,
                'violations': interview.proctoring_violations,
                'is_flagged': interview.is_flagged,
                'date': interview.created_at.isoformat() if interview.created_at else ''
            })

        return jsonify({'interviews': results})
    finally:
        db.close()


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    if request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum 10MB allowed.'}), 413


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Too many requests. Please try again later.'}), 429


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
