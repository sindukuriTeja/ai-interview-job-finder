# AI Interview & Job Finder Platform

An AI-powered technical interview system with integrated multi-platform job search engine. Built with Flask, SQLAlchemy, and Ollama LLM integration.

## Features

### AI Interview System
- **Resume Parsing** - Upload PDF/DOCX resumes for automatic skill extraction
- **AI Question Generation** - LLM-powered + rule-based interview questions tailored to candidate's skills
- **Real-time Proctoring** - Face detection, tab-switch monitoring, copy-paste detection
- **Automated Scoring** - AI evaluates answers on relevance, completeness, accuracy, and communication
- **Admin Dashboard** - Monitor interviews, flag suspicious activity, view audit logs
- **Anti-cheating** - Auto-terminates interviews after excessive violations

### Job Search Engine
- **Multi-platform Search** - Searches across 20+ job platforms simultaneously
- **Resume Analysis** - Extracts skills and suggests matching job titles
- **Smart Matching** - Ranks jobs by relevance to candidate's profile
- **Multiple Modes** - Jobs, Freelance, Clients, Influencers, Sponsors

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask, SQLAlchemy, Gunicorn |
| Database | SQLite (dev) / PostgreSQL (prod) |
| AI/LLM | Ollama (llama3.2) |
| Frontend | Vanilla JS, face-api.js |
| Proctoring | face-api.js (TinyFaceDetector) |
| Deployment | Docker, Docker Compose |

## Quick Start

### Prerequisites
- Python 3.9+
- Ollama (optional, for AI-powered features)

### Installation

```bash
# Clone the repository
git clone https://github.com/sindukuriTeja/ai-interview-job-finder.git
cd ai-interview-job-finder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the application
python run.py
```

### Docker Deployment

```bash
docker-compose up --build
```

The app will be available at `http://localhost:5000`

## Project Structure

```
ai-interview-job-finder/
├── app.py                  # Main Flask application
├── config.py               # Configuration settings
├── models.py               # SQLAlchemy database models
├── security.py             # Security utilities (rate limiting, sanitization)
├── job_search.py           # Job search module with 20+ platform scrapers
├── run.py                  # Application entry point
├── services/
│   ├── evaluator.py        # Answer evaluation (AI + rule-based)
│   ├── question_generator.py  # Question generation engine
│   ├── ollama_client.py    # Ollama LLM client
│   ├── resume_parser.py    # Resume parsing service
│   └── notifier.py         # Email notification service
├── templates/              # HTML templates
├── static/
│   ├── css/               # Stylesheets
│   ├── js/                # JavaScript (proctoring, recording)
│   └── models/            # Face detection ML models
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## API Endpoints

### Interview System
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload resume |
| POST | `/start-interview/<id>` | Start interview |
| POST | `/submit-answer` | Submit answer |
| POST | `/complete-interview/<id>` | Complete interview |
| GET | `/api/results/<id>` | Get results |

### Job Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze-resume` | Analyze resume for skills |
| POST | `/api/search` | Search jobs across platforms |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/login` | Admin login |
| GET | `/admin/api/stats` | Dashboard statistics |
| POST | `/admin/api/terminate/<id>` | Terminate interview |

## Security Features

- Rate limiting (per-IP, per-endpoint)
- Input sanitization (XSS prevention)
- Security headers (X-Frame-Options, CSP, etc.)
- Session management with secure cookies
- Audit logging for all admin actions
- File type validation (MIME + extension)

## Configuration

Key environment variables (see `.env.example`):

```
SECRET_KEY=your-secret-key
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
```

## Screenshots

*Coming soon*

## License

MIT License

## Author

Built by [sindukuriTeja](https://github.com/sindukuriTeja)
