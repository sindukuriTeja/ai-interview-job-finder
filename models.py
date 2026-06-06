from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.pool import QueuePool
from datetime import datetime
from config import Config

Base = declarative_base()
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    poolclass=QueuePool
)
Session = sessionmaker(bind=engine)


class Admin(Base):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)


class JobUser(Base):
    __tablename__ = 'job_users'

    id = Column(Integer, primary_key=True)
    display_name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(256))
    provider = Column(String(50), default='email')
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)


class Candidate(Base):
    __tablename__ = 'candidates'

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    email = Column(String(200))
    phone = Column(String(50))
    resume_path = Column(String(500))
    skills = Column(Text)
    experience_years = Column(Integer, default=0)
    education = Column(Text)
    job_titles = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    interviews = relationship('Interview', back_populates='candidate')

    __table_args__ = (
        Index('idx_candidate_email', 'email'),
        Index('idx_candidate_created', 'created_at'),
    )


class Interview(Base):
    __tablename__ = 'interviews'

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey('candidates.id'))
    status = Column(String(50), default='pending')
    total_score = Column(Float, default=0.0)
    total_questions = Column(Integer, default=0)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    recording_path = Column(String(500))
    proctoring_violations = Column(Integer, default=0)
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(Text)
    browser_fingerprint = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship('Candidate', back_populates='interviews')
    questions = relationship('Question', back_populates='interview')
    answers = relationship('Answer', back_populates='interview')
    proctor_logs = relationship('ProctorLog', back_populates='interview')

    __table_args__ = (
        Index('idx_interview_status', 'status'),
        Index('idx_interview_candidate', 'candidate_id'),
        Index('idx_interview_created', 'created_at'),
    )


class Question(Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey('interviews.id'))
    question_text = Column(Text)
    category = Column(String(100))
    difficulty = Column(String(50))
    skill_targeted = Column(String(200))
    order_num = Column(Integer)
    source = Column(String(50))

    interview = relationship('Interview', back_populates='questions')

    __table_args__ = (
        Index('idx_question_interview', 'interview_id'),
    )


class Answer(Base):
    __tablename__ = 'answers'

    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey('interviews.id'))
    question_id = Column(Integer, ForeignKey('questions.id'))
    answer_text = Column(Text)
    audio_path = Column(String(500))
    relevance_score = Column(Float, default=0.0)
    completeness_score = Column(Float, default=0.0)
    accuracy_score = Column(Float, default=0.0)
    communication_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    feedback = Column(Text)
    time_taken_seconds = Column(Integer)
    paste_detected = Column(Boolean, default=False)
    answered_at = Column(DateTime, default=datetime.utcnow)

    interview = relationship('Interview', back_populates='answers')
    question = relationship('Question')

    __table_args__ = (
        Index('idx_answer_interview', 'interview_id'),
    )


class ProctorLog(Base):
    __tablename__ = 'proctor_logs'

    id = Column(Integer, primary_key=True)
    interview_id = Column(Integer, ForeignKey('interviews.id'))
    violation_type = Column(String(100))
    description = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    severity = Column(String(50))
    extra_data = Column(Text)

    interview = relationship('Interview', back_populates='proctor_logs')

    __table_args__ = (
        Index('idx_proctor_interview', 'interview_id'),
        Index('idx_proctor_severity', 'severity'),
    )


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    action = Column(String(100), nullable=False)
    actor = Column(String(200))
    target_type = Column(String(50))
    target_id = Column(Integer)
    details = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_audit_action', 'action'),
        Index('idx_audit_timestamp', 'timestamp'),
    )


def init_db():
    Base.metadata.create_all(engine)


if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
