import json
import os
import re
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from flask import jsonify, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

from config import Config
from models import Session, JobUser
from security import sanitize_input, verify_password, hash_password
from datetime import datetime

ua = UserAgent()


def is_job_search_file_allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in getattr(Config, 'ALLOWED_SEARCH_EXTENSIONS', {'pdf', 'docx', 'txt'})


def extract_text_from_pdf(filepath):
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except Exception:
        pass

    try:
        import PyPDF2
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except Exception:
        return ""


def extract_text_from_docx(filepath):
    try:
        from docx import Document
        doc = Document(filepath)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception:
        return ""


def extract_text_from_file(filepath):
    ext = filepath.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        return extract_text_from_pdf(filepath)
    elif ext in ('docx', 'doc'):
        return extract_text_from_docx(filepath)
    elif ext == 'txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    return ""


def analyze_resume_text(text):
    text_lower = text.lower()
    found_skills = {}
    all_found = []

    for category, skills in SKILL_KEYWORDS.items():
        matched = []
        for skill in skills:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                matched.append(skill)
                all_found.append(skill)
        if matched:
            found_skills[category] = matched

    experience_years = 0
    year_patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
        r'experience.*?(\d+)\+?\s*years?',
        r'(\d+)\+?\s*years?\s*in',
    ]
    for pattern in year_patterns:
        match = re.search(pattern, text_lower)
        if match:
            experience_years = max(experience_years, int(match.group(1)))

    education = []
    edu_keywords = [
        'bachelor', 'master', 'phd', 'mba', 'b.tech', 'm.tech',
        'b.e.', 'm.e.', 'b.sc', 'm.sc', 'diploma', 'certification'
    ]
    for kw in edu_keywords:
        if kw in text_lower:
            education.append(kw.title())

    suggested_titles = []
    for skill in all_found:
        if skill in JOB_TITLE_MAPPING:
            suggested_titles.extend(JOB_TITLE_MAPPING[skill])

    for skill in found_skills.get('roles', []):
        if skill in JOB_TITLE_MAPPING:
            suggested_titles.extend(JOB_TITLE_MAPPING[skill])
        else:
            suggested_titles.append(skill.title())

    if not suggested_titles:
        if found_skills.get('programming'):
            suggested_titles.append('Software Developer')
        if found_skills.get('data'):
            suggested_titles.append('Data Scientist')
        if found_skills.get('cloud_devops'):
            suggested_titles.append('DevOps Engineer')

    suggested_titles = list(dict.fromkeys(suggested_titles))[:5]

    return {
        'skills': found_skills,
        'all_skills': all_found,
        'experience_years': experience_years,
        'education': education,
        'suggested_titles': suggested_titles,
        'summary': generate_profile_summary(found_skills, experience_years, education),
    }


def generate_profile_summary(skills, years, education):
    parts = []
    if years > 0:
        parts.append(f"{years}+ years experience")
    if skills.get('programming'):
        parts.append(f"Languages: {', '.join(skills['programming'][:5])}")
    if skills.get('frameworks'):
        parts.append(f"Frameworks: {', '.join(skills['frameworks'][:4])}")
    if skills.get('data'):
        parts.append(f"Data/AI: {', '.join(skills['data'][:3])}")
    if skills.get('cloud_devops'):
        parts.append(f"Cloud/DevOps: {', '.join(skills['cloud_devops'][:3])}")
    if education:
        parts.append(f"Education: {', '.join(education[:2])}")
    return ' | '.join(parts) if parts else 'General profile'


def score_job_match(job, resume_data):
    score = 0
    job_text = f"{job['title']} {job['company']} {job.get('description', '')}".lower()

    for skill in resume_data['all_skills']:
        if skill in job_text:
            score += 10

    for title in resume_data['suggested_titles']:
        if title.lower() in job_text:
            score += 20

    if any(role in job_text for role in resume_data['skills'].get('roles', [])):
        score += 15

    return score


def get_headers():
    return {
        'User-Agent': ua.random,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }


def register_job_search_routes(app, login_required):
    @app.route('/jobs')
    def jobs_landing():
        if 'user' in session:
            return redirect(url_for('dashboard'))
        return render_template('job_search/landing.html')

    @app.route('/login')
    def login():
        if 'user' in session:
            return redirect(url_for('dashboard'))
        return render_template('job_search/login.html')

    @app.route('/signup')
    def signup():
        if 'user' in session:
            return redirect(url_for('dashboard'))
        return render_template('job_search/signup.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('job_search/dashboard.html', user=session.get('user'))

    @app.route('/profile')
    @login_required
    def profile():
        return render_template('job_search/profile.html', user=session.get('user'))

    @app.route('/api/auth/login', methods=['POST'])
    def login_user():
        data = request.get_json() or {}
        email = sanitize_input(data.get('email', '')).lower()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        db = Session()
        user = db.query(JobUser).filter_by(email=email).first()
        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            db.close()
            return jsonify({'error': 'Invalid email or password'}), 401

        user.last_login = datetime.utcnow()
        db.commit()
        session['user'] = {
            'uid': str(user.id),
            'email': user.email,
            'displayName': user.display_name,
            'provider': user.provider,
        }
        db.close()
        return jsonify({'success': True, 'user': session['user']})

    @app.route('/api/auth/signup', methods=['POST'])
    def signup_user():
        data = request.get_json() or {}
        display_name = sanitize_input(data.get('displayName', ''))
        email = sanitize_input(data.get('email', '')).lower()
        password = data.get('password', '')

        if not display_name or not email or not password:
            return jsonify({'error': 'Name, email, and password are required'}), 400

        db = Session()
        if db.query(JobUser).filter_by(email=email).first():
            db.close()
            return jsonify({'error': 'A user with this email already exists'}), 409

        user = JobUser(
            display_name=display_name,
            email=email,
            password_hash=hash_password(password),
            provider='email'
        )
        db.add(user)
        db.commit()
        session['user'] = {
            'uid': str(user.id),
            'email': user.email,
            'displayName': user.display_name,
            'provider': user.provider,
        }
        db.close()
        return jsonify({'success': True, 'user': session['user']})

    @app.route('/api/auth/session', methods=['POST'])
    def create_session():
        data = request.get_json()
        if not data or 'user' not in data:
            return jsonify({'error': 'No user data provided'}), 400

        user_data = data['user']
        session['user'] = {
            'uid': user_data.get('uid', ''),
            'email': user_data.get('email', ''),
            'displayName': user_data.get('displayName', ''),
            'photoURL': user_data.get('photoURL', ''),
            'provider': user_data.get('provider', ''),
        }
        return jsonify({'success': True, 'user': session['user']})

    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        session.pop('user', None)
        return jsonify({'success': True})

    @app.route('/api/auth/status')
    def auth_status():
        if 'user' in session:
            return jsonify({'authenticated': True, 'user': session['user']})
        return jsonify({'authenticated': False})

    @app.route('/api/analyze-resume', methods=['POST'])
    @login_required
    def analyze_resume_endpoint():
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file uploaded'}), 400

        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not is_job_search_file_allowed(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PDF, DOCX, or TXT'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            text = extract_text_from_file(filepath)
            if not text.strip():
                os.remove(filepath)
                return jsonify({'error': 'Could not extract text from resume. Please try a different format.'}), 400

            resume_data = analyze_resume_text(text)
            os.remove(filepath)
            return jsonify({
                'success': True,
                'profile': resume_data,
            })
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Failed to analyze resume. Please try again later.'}), 500

    @app.route('/api/search', methods=['POST'])
    @login_required
    def search_jobs_route():
        data = request.get_json() or {}
        queries = data.get('queries', [])
        location = data.get('location', '').strip()
        resume_skills = data.get('resume_skills', [])
        suggested_titles = data.get('suggested_titles', [])
        search_mode = data.get('mode', 'jobs')

        if not queries:
            return jsonify({'error': 'No search queries provided'}), 400

        all_jobs = []
        seen_links = set()

        for query in queries[:3]:
            with ThreadPoolExecutor(max_workers=12) as executor:
                futures = {}

                if search_mode in ('jobs', 'both'):
                    futures[executor.submit(search_google_jobs, query, location)] = 'Google'
                    futures[executor.submit(search_linkedin_jobs, query, location)] = 'LinkedIn'
                    futures[executor.submit(search_indeed_jobs, query, location)] = 'Indeed'
                    futures[executor.submit(search_glassdoor_jobs, query, location)] = 'Glassdoor'
                    futures[executor.submit(search_remoteok_jobs, query, location)] = 'RemoteOK'

                if search_mode in ('freelance', 'both'):
                    futures[executor.submit(search_upwork_gigs, query, location)] = 'Upwork'
                    futures[executor.submit(search_freelancer_gigs, query, location)] = 'Freelancer'
                    futures[executor.submit(search_fiverr_gigs, query, location)] = 'Fiverr'
                    futures[executor.submit(search_toptal_gigs, query, location)] = 'Toptal'
                    futures[executor.submit(search_guru_gigs, query, location)] = 'Guru'

                if search_mode == 'clients':
                    futures[executor.submit(search_angellist_startups, query, location)] = 'AngelList'
                    futures[executor.submit(search_producthunt_startups, query, location)] = 'ProductHunt'
                    futures[executor.submit(search_craigslist_gigs, query, location)] = 'Craigslist'
                    futures[executor.submit(search_peopleperhour_projects, query, location)] = 'PeoplePerHour'
                    futures[executor.submit(search_contra_projects, query, location)] = 'Contra'
                    futures[executor.submit(search_99designs_contests, query, location)] = '99designs'

                if search_mode == 'influencers':
                    futures[executor.submit(search_youtube_influencers, query, location)] = 'YouTube'
                    futures[executor.submit(search_tiktok_influencers, query, location)] = 'TikTok'
                    futures[executor.submit(search_instagram_influencers, query, location)] = 'Instagram'
                    futures[executor.submit(search_influencer_marketing_hub, query, location)] = 'IMHub'
                    futures[executor.submit(search_heepsy_influencers, query, location)] = 'Heepsy'
                    futures[executor.submit(search_upfluence_influencers, query, location)] = 'Upfluence'
                    futures[executor.submit(search_collabstr_influencers, query, location)] = 'Collabstr'

                if search_mode == 'sponsors':
                    futures[executor.submit(search_sponsorship_opportunities, query, location)] = 'SponsorSearch'
                    futures[executor.submit(search_grapevine_sponsors, query, location)] = 'Grapevine'
                    futures[executor.submit(search_aspire_sponsors, query, location)] = 'Aspire'
                    futures[executor.submit(search_brandbass_sponsors, query, location)] = 'Brandbassador'
                    futures[executor.submit(search_izea_sponsors, query, location)] = 'IZEA'
                    futures[executor.submit(search_hashtag_paid_sponsors, query, location)] = 'HashtagPaid'
                    futures[executor.submit(search_youtube_brandconnect, query, location)] = 'BrandConnect'
                    futures[executor.submit(search_sponsor_directory, query, location)] = 'SponsorGap'

                for future in futures:
                    try:
                        jobs = future.result()
                        for job in jobs:
                            apply_link = job.get('apply_link') or ''
                            if apply_link not in seen_links:
                                seen_links.add(apply_link)
                                all_jobs.append(job)
                    except Exception:
                        continue

        if resume_skills:
            resume_data = {'all_skills': resume_skills, 'suggested_titles': suggested_titles, 'skills': {'roles': []}}
            for job in all_jobs:
                job['match_score'] = score_job_match(job, resume_data)
            all_jobs.sort(key=lambda x: x.get('match_score', 0), reverse=True)

        return jsonify({
            'jobs': all_jobs,
            'total': len(all_jobs),
            'queries': queries,
            'location': location,
            'mode': search_mode,
        })


SKILL_KEYWORDS = {
    'programming': [
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'go',
        'rust', 'php', 'swift', 'kotlin', 'scala', 'r', 'matlab', 'perl',
        'html', 'css', 'sql', 'bash', 'shell', 'powershell',
    ],
    'frameworks': [
        'react', 'angular', 'vue', 'django', 'flask', 'spring', 'node.js',
        'express', 'fastapi', 'laravel', 'rails', 'next.js', 'nuxt',
        '.net', 'tensorflow', 'pytorch', 'keras', 'scikit-learn',
        'bootstrap', 'tailwind', 'flutter', 'react native',
    ],
    'data': [
        'machine learning', 'deep learning', 'data science', 'data analysis',
        'data engineering', 'big data', 'analytics', 'statistics',
        'nlp', 'natural language processing', 'computer vision',
        'artificial intelligence', 'ai', 'ml', 'neural network',
        'pandas', 'numpy', 'spark', 'hadoop', 'tableau', 'power bi',
    ],
    'cloud_devops': [
        'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes',
        'jenkins', 'terraform', 'ansible', 'ci/cd', 'devops',
        'linux', 'microservices', 'serverless', 'lambda',
    ],
    'databases': [
        'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
        'dynamodb', 'oracle', 'sql server', 'cassandra', 'firebase',
    ],
    'roles': [
        'software engineer', 'developer', 'full stack', 'frontend',
        'backend', 'data scientist', 'data analyst', 'data engineer',
        'devops engineer', 'cloud engineer', 'ml engineer',
        'product manager', 'project manager', 'ui/ux', 'designer',
        'mobile developer', 'ios developer', 'android developer',
        'qa engineer', 'test engineer', 'security engineer',
        'system administrator', 'network engineer', 'dba',
        'business analyst', 'scrum master', 'tech lead',
        'solutions architect', 'web developer', 'site reliability',
    ],
    'soft_skills': [
        'leadership', 'communication', 'teamwork', 'agile', 'scrum',
        'problem solving', 'project management', 'collaboration',
    ],
}

JOB_TITLE_MAPPING = {
    'python': ['Python Developer', 'Python Engineer', 'Backend Developer Python'],
    'java': ['Java Developer', 'Java Engineer', 'Backend Developer Java'],
    'javascript': ['JavaScript Developer', 'Frontend Developer', 'Full Stack Developer'],
    'react': ['React Developer', 'Frontend Engineer', 'React.js Developer'],
    'angular': ['Angular Developer', 'Frontend Engineer Angular'],
    'vue': ['Vue.js Developer', 'Frontend Developer Vue'],
    'node.js': ['Node.js Developer', 'Backend Developer', 'Full Stack Node'],
    'django': ['Django Developer', 'Python Backend Developer'],
    'flask': ['Flask Developer', 'Python Backend Developer'],
    'machine learning': ['ML Engineer', 'Machine Learning Engineer', 'AI Engineer'],
    'data science': ['Data Scientist', 'Senior Data Scientist'],
    'data analysis': ['Data Analyst', 'Business Analyst', 'Analytics Engineer'],
    'data engineering': ['Data Engineer', 'Big Data Engineer'],
    'aws': ['AWS Engineer', 'Cloud Engineer AWS', 'DevOps Engineer'],
    'azure': ['Azure Engineer', 'Cloud Engineer Azure'],
    'docker': ['DevOps Engineer', 'Platform Engineer'],
    'kubernetes': ['DevOps Engineer', 'Kubernetes Engineer', 'Platform Engineer'],
    'mobile developer': ['Mobile Developer', 'App Developer'],
    'ios developer': ['iOS Developer', 'Swift Developer'],
    'android developer': ['Android Developer', 'Kotlin Developer'],
    'ui/ux': ['UI/UX Designer', 'Product Designer', 'UX Designer'],
    'product manager': ['Product Manager', 'Senior Product Manager'],
    'project manager': ['Project Manager', 'Technical Project Manager'],
    'full stack': ['Full Stack Developer', 'Full Stack Engineer'],
    'frontend': ['Frontend Developer', 'Frontend Engineer'],
    'backend': ['Backend Developer', 'Backend Engineer'],
    'devops engineer': ['DevOps Engineer', 'Site Reliability Engineer'],
    'cloud engineer': ['Cloud Engineer', 'Cloud Architect'],
    'security engineer': ['Security Engineer', 'Cybersecurity Engineer'],
    'qa engineer': ['QA Engineer', 'Test Automation Engineer'],
}


# Search functions

# the following functions are intentionally kept in the same order as the original job-search app

def search_google_jobs(query, location=''):
    jobs = []
    search_query = f"{query} jobs"
    if location:
        search_query += f" in {location}"

    url = 'https://www.google.com/search'
    params = {'q': search_query, 'ibp': 'htl;jobs', 'hl': 'en'}

    try:
        resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        job_cards = soup.find_all('div', class_='BjJfJf')
        if not job_cards:
            job_cards = soup.find_all('li', class_='iFjolb')

        for card in job_cards[:20]:
            title_el = card.find('div', class_='BjJfJf') or card.find('h2') or card.find('div', class_='tJ9zfc')
            company_el = card.find('div', class_='vNEEBe') or card.find('span', class_='vNEEBe')
            location_el = card.find('div', class_='Qk80Jf') or card.find('span', class_='Qk80Jf')

            title = title_el.get_text(strip=True) if title_el else ''
            company = company_el.get_text(strip=True) if company_el else ''
            job_location = location_el.get_text(strip=True) if location_el else ''

            if title:
                apply_link = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}&ibp=htl;jobs"
                jobs.append({
                    'title': title, 'company': company, 'location': job_location,
                    'source': 'Google Jobs', 'apply_link': apply_link, 'description': '',
                })
    except Exception:
        pass

    if not jobs:
        apply_link = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}&ibp=htl;jobs"
        jobs.append({
            'title': f'{query}', 'company': 'Multiple Companies',
            'location': location or 'Various', 'source': 'Google Jobs',
            'apply_link': apply_link, 'description': 'View all matching jobs on Google Jobs',
        })
    return jobs


def search_linkedin_jobs(query, location=''):
    jobs = []
    params = {'keywords': query, 'location': location or '', 'position': '1', 'pageNum': '0'}
    url = 'https://www.linkedin.com/jobs/search/'

    try:
        resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        job_cards = soup.find_all('div', class_='base-card')
        if not job_cards:
            job_cards = soup.find_all('li', class_='result-card')

        for card in job_cards[:15]:
            title_el = card.find('h3', class_='base-search-card__title') or card.find('h3')
            company_el = card.find('h4', class_='base-search-card__subtitle') or card.find('h4')
            location_el = card.find('span', class_='job-search-card__location')
            link_el = card.find('a', class_='base-card__full-link') or card.find('a')

            title = title_el.get_text(strip=True) if title_el else ''
            company = company_el.get_text(strip=True) if company_el else ''
            job_location = location_el.get_text(strip=True) if location_el else ''
            apply_link = link_el['href'] if link_el and link_el.get('href') else ''

            if title and apply_link:
                jobs.append({
                    'title': title, 'company': company, 'location': job_location,
                    'source': 'LinkedIn', 'apply_link': apply_link, 'description': '',
                })
    except Exception:
        pass

    if not jobs:
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(query)}"
        if location:
            search_url += f"&location={urllib.parse.quote(location)}"
        jobs.append({
            'title': f'{query}', 'company': 'Multiple Companies',
            'location': location or 'Various', 'source': 'LinkedIn',
            'apply_link': search_url, 'description': 'View all matching jobs on LinkedIn',
        })
    return jobs


def search_indeed_jobs(query, location=''):
    jobs = []
    params = {'q': query, 'l': location or ''}
    url = 'https://www.indeed.com/jobs'

    try:
        resp = requests.get(url, params=params, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        job_cards = soup.find_all('div', class_='job_seen_beacon')

        for card in job_cards[:15]:
            title_el = card.find('h2', class_='jobTitle')
            company_el = card.find('span', attrs={'data-testid': 'company-name'})
            location_el = card.find('div', attrs={'data-testid': 'text-location'})
            link_el = card.find('a', href=True)

            title = title_el.get_text(strip=True) if title_el else ''
            company = company_el.get_text(strip=True) if company_el else ''
            job_location = location_el.get_text(strip=True) if location_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = f'https://www.indeed.com{href}' if href.startswith('/') else href

            if title:
                jobs.append({
                    'title': title, 'company': company, 'location': job_location,
                    'source': 'Indeed',
                    'apply_link': apply_link or f'https://www.indeed.com/jobs?q={urllib.parse.quote(query)}&l={urllib.parse.quote(location or '')}',
                    'description': '',
                })
    except Exception:
        pass

    if not jobs:
        search_url = f'https://www.indeed.com/jobs?q={urllib.parse.quote(query)}'
        if location:
            search_url += f'&l={urllib.parse.quote(location)}'
        jobs.append({
            'title': f'{query}', 'company': 'Multiple Companies',
            'location': location or 'Various', 'source': 'Indeed',
            'apply_link': search_url, 'description': 'View all matching jobs on Indeed',
        })
    return jobs


def search_glassdoor_jobs(query, location=''):
    search_url = f'https://www.glassdoor.com/Job/jobs.htm?sc.keyword={urllib.parse.quote(query)}'
    if location:
        search_url += f'&locT=C&locKeyword={urllib.parse.quote(location)}'
    return [{
        'title': f'{query}', 'company': 'Multiple Companies',
        'location': location or 'Various', 'source': 'Glassdoor',
        'apply_link': search_url, 'description': 'View all matching jobs on Glassdoor',
    }]


def search_remoteok_jobs(query, location=''):
    jobs = []
    try:
        tag = query.lower().replace(' ', '-')
        url = f'https://remoteok.com/api?tag={tag}'
        resp = requests.get(url, headers=get_headers(), timeout=10)
        data = resp.json()

        for item in data[1:16]:
            title = item.get('position', '')
            company = item.get('company', '')
            job_location = item.get('location', 'Remote')
            apply_link = item.get('url', '')

            if title:
                jobs.append({
                    'title': title, 'company': company,
                    'location': job_location or 'Remote', 'source': 'RemoteOK',
                    'apply_link': apply_link, 'description': '',
                })
    except Exception:
        pass

    if not jobs:
        tag = query.lower().replace(' ', '-')
        jobs.append({
            'title': f'Remote {query}', 'company': 'Multiple Companies',
            'location': 'Remote', 'source': 'RemoteOK',
            'apply_link': f'https://remoteok.com/remote-{tag}-jobs',
            'description': 'View all matching remote jobs',
        })
    return jobs


def search_upwork_gigs(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://www.upwork.com/nx/search/jobs/?q={search_query}&sort=recency'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        job_cards = soup.find_all('section', class_='up-card-section')
        if not job_cards:
            job_cards = soup.find_all('div', attrs={'data-test': 'JobTile'})

        for card in job_cards[:15]:
            title_el = card.find('a', class_='up-n-link')
            budget_el = card.find('span', attrs={'data-test': 'budget'}) or card.find('span', class_='js-budget')
            desc_el = card.find('span', class_='js-description-text') or card.find('p')

            title = title_el.get_text(strip=True) if title_el else ''
            budget = budget_el.get_text(strip=True) if budget_el else ''
            description = desc_el.get_text(strip=True)[:150] if desc_el else ''
            apply_link = ''
            if title_el and title_el.get('href'):
                href = title_el['href']
                apply_link = f'https://www.upwork.com{href}' if href.startswith('/') else href

            if title:
                jobs.append({
                    'title': title, 'company': 'Upwork Client',
                    'location': 'Remote', 'source': 'Upwork',
                    'apply_link': apply_link or url,
                    'description': f'{budget} - {description}' if budget else description,
                    'type': 'freelance',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'{query} - Freelance Projects', 'company': 'Multiple Clients',
            'location': 'Remote', 'source': 'Upwork',
            'apply_link': url,
            'description': 'View all matching freelance projects on Upwork',
            'type': 'freelance',
        })
    return jobs


def search_freelancer_gigs(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://www.freelancer.com/jobs/{search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        job_cards = soup.find_all('div', class_='JobSearchCard-item')
        if not job_cards:
            job_cards = soup.find_all('div', class_='project-card')

        for card in job_cards[:15]:
            title_el = card.find('a', class_='JobSearchCard-primary-heading-link')
            budget_el = card.find('div', class_='JobSearchCard-primary-price')
            desc_el = card.find('p', class_='JobSearchCard-primary-description')

            title = title_el.get_text(strip=True) if title_el else ''
            budget = budget_el.get_text(strip=True) if budget_el else ''
            description = desc_el.get_text(strip=True)[:150] if desc_el else ''
            apply_link = ''
            if title_el and title_el.get('href'):
                href = title_el['href']
                apply_link = f'https://www.freelancer.com{href}' if href.startswith('/') else href

            if title:
                jobs.append({
                    'title': title, 'company': 'Freelancer Client',
                    'location': 'Remote', 'source': 'Freelancer',
                    'apply_link': apply_link or url,
                    'description': f'{budget} - {description}' if budget else description,
                    'type': 'freelance',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'{query} - Freelance Projects', 'company': 'Multiple Clients',
            'location': 'Remote', 'source': 'Freelancer',
            'apply_link': url,
            'description': 'View all matching freelance projects on Freelancer.com',
            'type': 'freelance',
        })
    return jobs


def search_fiverr_gigs(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://www.fiverr.com/search/gigs?query={search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        gig_cards = soup.find_all('div', class_='gig-card-layout')
        if not gig_cards:
            gig_cards = soup.find_all('div', attrs={'class': re.compile(r'gig-wrapper')})

        for card in gig_cards[:15]:
            title_el = card.find('a', class_='gig-title') or card.find('h3') or card.find('p', class_='text-display-7')
            seller_el = card.find('a', class_='seller-name') or card.find('span', class_='username')
            price_el = card.find('span', class_='price') or card.find('a', class_='price')
            link_el = card.find('a', href=True)

            title = title_el.get_text(strip=True) if title_el else ''
            seller = seller_el.get_text(strip=True) if seller_el else 'Fiverr Seller'
            price = price_el.get_text(strip=True) if price_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = f'https://www.fiverr.com{href}' if href.startswith('/') else href

            if title:
                jobs.append({
                    'title': title, 'company': seller,
                    'location': 'Remote', 'source': 'Fiverr',
                    'apply_link': apply_link or url,
                    'description': f'Starting at {price}' if price else 'View gig details',
                    'type': 'freelance',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'{query} - Gigs & Services', 'company': 'Multiple Sellers',
            'location': 'Remote', 'source': 'Fiverr',
            'apply_link': url,
            'description': 'View all matching gigs on Fiverr',
            'type': 'freelance',
        })
    return jobs


def search_toptal_gigs(query, location=''):
    url = 'https://www.toptal.com/freelance-jobs'
    return [{
        'title': f'{query} - Freelance Opportunities', 'company': 'Toptal Network',
        'location': 'Remote', 'source': 'Toptal',
        'apply_link': url, 'description': 'View all matching remote jobs on Toptal',
        'type': 'freelance',
    }]


def search_guru_gigs(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://www.guru.com/d/jobs/q/{search_query}/'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        job_cards = soup.find_all('div', class_='jobRecord')
        if not job_cards:
            job_cards = soup.find_all('div', class_='record')

        for card in job_cards[:15]:
            title_el = card.find('h2') or card.find('a', class_='jobRecord__title')
            budget_el = card.find('span', class_='budget') or card.find('div', class_='jobRecord__budget')
            link_el = card.find('a', href=True)

            title = title_el.get_text(strip=True) if title_el else ''
            budget = budget_el.get_text(strip=True) if budget_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = f'https://www.guru.com{href}' if href.startswith('/') else href

            if title:
                jobs.append({
                    'title': title, 'company': 'Guru Client',
                    'location': 'Remote', 'source': 'Guru',
                    'apply_link': apply_link or url,
                    'description': budget if budget else 'View project details',
                    'type': 'freelance',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'{query} - Freelance Projects', 'company': 'Multiple Clients',
            'location': 'Remote', 'source': 'Guru',
            'apply_link': url,
            'description': 'View all matching freelance projects on Guru',
            'type': 'freelance',
        })
    return jobs


def search_angellist_startups(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://wellfound.com/role/{search_query.lower().replace('%20', '-')}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        startup_cards = soup.find_all('div', class_='styles_component__')
        if not startup_cards:
            startup_cards = soup.find_all('div', class_='startup-row')

        for card in startup_cards[:15]:
            name_el = card.find('h2') or card.find('a', class_='startup-link')
            desc_el = card.find('span', class_='text-neutral-1000') or card.find('p')
            link_el = card.find('a', href=True)

            name = name_el.get_text(strip=True) if name_el else ''
            description = desc_el.get_text(strip=True)[:150] if desc_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = f'https://wellfound.com{href}' if href.startswith('/') else href

            if name:
                jobs.append({
                    'title': f'{name} - Looking for {query}',
                    'company': name,
                    'location': location or 'Remote',
                    'source': 'AngelList',
                    'apply_link': apply_link or url,
                    'description': description or 'Startup looking for talent',
                    'type': 'client',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'Startups needing {query}', 'company': 'Multiple Startups',
            'location': location or 'Remote', 'source': 'AngelList',
            'apply_link': f'https://wellfound.com/role/{search_query.lower().replace('%20', '-')}',
            'description': 'Browse startups looking for your services on AngelList/Wellfound',
            'type': 'client',
        })
    return jobs


def search_producthunt_startups(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://www.producthunt.com/search?q={search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        product_cards = soup.find_all('div', attrs={'data-test': 'post-item'})
        if not product_cards:
            product_cards = soup.find_all('li', class_='styles_item__')

        for card in product_cards[:15]:
            name_el = card.find('a', attrs={'data-test': 'post-name'}) or card.find('h3')
            tagline_el = card.find('p') or card.find('a', attrs={'data-test': 'post-tagline'})
            link_el = card.find('a', href=True)

            name = name_el.get_text(strip=True) if name_el else ''
            tagline = tagline_el.get_text(strip=True)[:150] if tagline_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = f'https://www.producthunt.com{href}' if href.startswith('/') else href

            if name:
                jobs.append({
                    'title': f'{name} - Potential Client',
                    'company': name,
                    'location': 'Remote',
                    'source': 'ProductHunt',
                    'apply_link': apply_link or url,
                    'description': tagline or 'New startup that may need your services',
                    'type': 'client',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'Startups related to {query}', 'company': 'New Startups',
            'location': 'Remote', 'source': 'ProductHunt',
            'apply_link': url,
            'description': 'Discover new startups that may need your services on ProductHunt',
            'type': 'client',
        })
    return jobs


def search_craigslist_gigs(query, location=''):
    jobs = []
    city = 'newyork'
    if location:
        city = location.lower().replace(' ', '').replace(',', '')[:20]
    search_query = urllib.parse.quote(query)
    url = f'https://{city}.craigslist.org/search/gig?query={search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        listings = soup.find_all('li', class_='cl-static-search-result') or soup.find_all('li', class_='result-row')

        for listing in listings[:15]:
            title_el = listing.find('div', class_='title') or listing.find('a', class_='posting-title') or listing.find('a')
            link_el = listing.find('a', href=True)

            title = title_el.get_text(strip=True) if title_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = href if href.startswith('http') else f'https://{city}.craigslist.org{href}'

            if title:
                jobs.append({
                    'title': title,
                    'company': 'Craigslist Client',
                    'location': location or 'Local',
                    'source': 'Craigslist',
                    'apply_link': apply_link or url,
                    'description': 'Client looking for freelance services',
                    'type': 'client',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'Clients needing {query}', 'company': 'Local Clients',
            'location': location or 'Various', 'source': 'Craigslist',
            'apply_link': url,
            'description': 'Browse gig postings from clients on Craigslist',
            'type': 'client',
        })
    return jobs


def search_peopleperhour_projects(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://www.peopleperhour.com/freelance-jobs?keyword={search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        project_cards = soup.find_all('div', class_='item-list--item')
        if not project_cards:
            project_cards = soup.find_all('div', class_='job-card')

        for card in project_cards[:15]:
            title_el = card.find('h5') or card.find('a', class_='item-list--item--title')
            budget_el = card.find('span', class_='budget') or card.find('div', class_='price')
            link_el = card.find('a', href=True)

            title = title_el.get_text(strip=True) if title_el else ''
            budget = budget_el.get_text(strip=True) if budget_el else ''
            desc_el = card.find('span', class_='js-description-text') or card.find('p')
            description = desc_el.get_text(strip=True)[:150] if desc_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = f'https://www.peopleperhour.com{href}' if href.startswith('/') else href

            if title:
                jobs.append({
                    'title': title,
                    'company': 'PeoplePerHour Client',
                    'location': 'Remote', 'source': 'PeoplePerHour',
                    'apply_link': apply_link or url,
                    'description': f'Budget: {budget}' if budget else 'Client project posting',
                    'type': 'client',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'Clients needing {query}', 'company': 'Multiple Clients',
            'location': 'Remote', 'source': 'PeoplePerHour',
            'apply_link': url,
            'description': 'Browse client project postings on PeoplePerHour',
            'type': 'client',
        })
    return jobs


def search_contra_projects(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(query)
    url = f'https://contra.com/search/projects?query={search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        project_cards = soup.find_all('div', attrs={'data-testid': 'project-card'})
        if not project_cards:
            project_cards = soup.find_all('article')

        for card in project_cards[:15]:
            title_el = card.find('h3') or card.find('a')
            desc_el = card.find('p')
            link_el = card.find('a', href=True)

            title = title_el.get_text(strip=True) if title_el else ''
            description = desc_el.get_text(strip=True)[:150] if desc_el else ''
            apply_link = ''
            if link_el and link_el.get('href'):
                href = link_el['href']
                apply_link = f'https://contra.com{href}' if href.startswith('/') else href

            if title:
                jobs.append({
                    'title': title,
                    'company': 'Contra Client',
                    'location': 'Remote', 'source': 'Contra',
                    'apply_link': apply_link or url,
                    'description': description or 'Commission-free freelance project',
                    'type': 'client',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'Projects needing {query}', 'company': 'Multiple Clients',
            'location': 'Remote', 'source': 'Contra',
            'apply_link': url,
            'description': 'Browse commission-free client projects on Contra',
            'type': 'client',
        })
    return jobs


def search_99designs_contests(query, location=''):
    search_query = urllib.parse.quote(query)
    url = f'https://99designs.com/contests?search={search_query}'
    return [{
        'title': f'{query} - Design Contests & Client Projects', 'company': 'Multiple Clients',
        'location': 'Remote', 'source': '99designs',
        'apply_link': url, 'description': 'Browse design contests and client briefs on 99designs',
        'type': 'client',
    }]


def search_youtube_influencers(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(f'{query} influencer collaboration')
    url = f'https://www.youtube.com/results?search_query={search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'videoRenderer' in script.string:
                matches = re.findall(r'"text":"([^"]{5,80})"', script.string)
                channels = re.findall(r'"ownerText":\{"runs":\[\{"text":"([^"]+)"', script.string)
                links = re.findall(r'"url":"(/watch\?v=[^\"]+)"', script.string)

                for i, (title, channel) in enumerate(zip(matches[:10], channels[:10])):
                    link = links[i] if i < len(links) else ''
                    apply_link = f'https://www.youtube.com{link}' if link else url
                    jobs.append({
                        'title': f'{channel} - {title[:50]}',
                        'company': channel,
                        'location': 'YouTube', 'source': 'YouTube',
                        'apply_link': apply_link,
                        'description': f'YouTube creator in {query} niche - potential collaboration partner',
                        'type': 'influencer',
                    })
                break
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'{query} Influencers on YouTube', 'company': 'YouTube Creators',
            'location': 'Global', 'source': 'YouTube',
            'apply_link': url, 'description': f'Find {query} content creators for collaborations on YouTube',
            'type': 'influencer',
        })
    return jobs


def search_tiktok_influencers(query, location=''):
    search_query = urllib.parse.quote(query)
    url = f'https://www.tiktok.com/search?q={search_query}+influencer'
    return [{
        'title': f'{query} TikTok Creators & Influencers', 'company': 'TikTok Creator Marketplace',
        'location': 'Global', 'source': 'TikTok',
        'apply_link': 'https://creatormarketplace.tiktok.com/',
        'description': f'Discover TikTok creators in {query} niche for brand deals & collaborations',
        'type': 'influencer',
    }]


def search_instagram_influencers(query, location=''):
    url = f'https://www.instagram.com/explore/tags/{query.lower().replace(' ', '')}/'
    return [{
        'title': f'{query} Instagram Influencers', 'company': 'Instagram Creators',
        'location': location or 'Global', 'source': 'Instagram',
        'apply_link': url, 'description': f'Find Instagram influencers and creators in the {query} space',
        'type': 'influencer',
    }]


def search_influencer_marketing_hub(query, location=''):
    url = 'https://influencermarketinghub.com/influencer-marketing-platforms/'
    return [{
        'title': f'Find {query} Influencers - Top Platforms', 'company': 'Influencer Marketing Hub',
        'location': location or 'Global', 'source': 'IMHub',
        'apply_link': url, 'description': 'Directory of influencer marketing platforms to find and connect with creators',
        'type': 'influencer',
    }]


def search_heepsy_influencers(query, location=''):
    search_query = urllib.parse.quote(query)
    url = f'https://www.heepsy.com/search?keyword={search_query}'
    return [{
        'title': f'{query} Influencers - Heepsy Database', 'company': 'Heepsy',
        'location': location or 'Global', 'source': 'Heepsy',
        'apply_link': url, 'description': f'Search 11M+ influencers in {query} niche with audience analytics & engagement data',
        'type': 'influencer',
    }]


def search_upfluence_influencers(query, location=''):
    url = 'https://www.upfluence.com/free-influencer-search'
    return [{
        'title': f'{query} Influencers - Upfluence', 'company': 'Upfluence',
        'location': location or 'Global', 'source': 'Upfluence',
        'apply_link': url, 'description': f'AI-powered influencer discovery platform - find {query} creators with real engagement',
        'type': 'influencer',
    }]


def search_collabstr_influencers(query, location=''):
    search_query = urllib.parse.quote(query)
    url = f'https://collabstr.com/search?query={search_query}'
    return [{
        'title': f'Hire {query} Influencers - Collabstr Marketplace', 'company': 'Collabstr Marketplace',
        'location': location or 'Global', 'source': 'Collabstr',
        'apply_link': url, 'description': f'Book verified {query} influencers for sponsored posts, stories & reels',
        'type': 'influencer',
    }]


def search_sponsorship_opportunities(query, location=''):
    jobs = []
    search_query = urllib.parse.quote(f'{query} sponsorship opportunity')
    url = f'https://www.google.com/search?q={search_query}'

    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = soup.find_all('div', class_='g')
        for result in results[:10]:
            title_el = result.find('h3')
            link_el = result.find('a', href=True)
            snippet_el = result.find('span', class_='st') or result.find('div', class_='VwiC3b')

            title = title_el.get_text(strip=True) if title_el else ''
            snippet = snippet_el.get_text(strip=True)[:150] if snippet_el else ''
            apply_link = link_el['href'] if link_el else ''

            if title and apply_link and apply_link.startswith('http'):
                jobs.append({
                    'title': title,
                    'company': 'Sponsorship Opportunity',
                    'location': location or 'Global',
                    'source': 'SponsorSearch',
                    'apply_link': apply_link,
                    'description': snippet or f'Sponsorship opportunity in {query}',
                    'type': 'sponsor',
                })
    except Exception:
        pass

    if not jobs:
        jobs.append({
            'title': f'{query} Sponsorship Opportunities', 'company': 'Various Brands',
            'location': location or 'Global', 'source': 'SponsorSearch',
            'apply_link': url, 'description': f'Search for {query} sponsorship and brand deal opportunities',
            'type': 'sponsor',
        })
    return jobs


def search_grapevine_sponsors(query, location=''):
    url = 'https://grapevinevillage.com/'
    return [{
        'title': f'Brand Sponsorships for {query} Creators', 'company': 'Grapevine Village',
        'location': 'Global', 'source': 'Grapevine',
        'apply_link': url, 'description': 'Connect with brands looking to sponsor content creators - get paid campaigns',
        'type': 'sponsor',
    }]


def search_aspire_sponsors(query, location=''):
    url = 'https://www.aspire.io/creators'
    return [{
        'title': f'{query} Brand Collaborations - AspireIQ', 'company': 'Aspire (AspireIQ)',
        'location': 'Global', 'source': 'Aspire',
        'apply_link': url, 'description': f"Join Aspire's creator community to get matched with {query} brands for paid sponsorships",
        'type': 'sponsor',
    }]


def search_brandbass_sponsors(query, location=''):
    url = 'https://www.brandbassador.com/creators'
    return [{
        'title': f'Become a {query} Brand Ambassador', 'company': 'Brandbassador',
        'location': 'Global', 'source': 'Brandbassador',
        'apply_link': url, 'description': f'Get paid as a {query} brand ambassador - earn through missions, referrals & content',
        'type': 'sponsor',
    }]


def search_izea_sponsors(query, location=''):
    url = 'https://izea.com/creators/'
    return [{
        'title': f'{query} Paid Sponsorships - IZEA', 'company': 'IZEA',
        'location': 'Global', 'source': 'IZEA',
        'apply_link': url, 'description': f'Get paid to create {query} content - brands post opportunities for creators',
        'type': 'sponsor',
    }]


def search_hashtag_paid_sponsors(query, location=''):
    url = 'https://hashtagpaid.com/creators'
    return [{
        'title': f'{query} Creator Campaigns - #paid', 'company': '#paid (Hashtag Paid)',
        'location': 'Global', 'source': 'HashtagPaid',
        'apply_link': url, 'description': f'Opt into {query} brand campaigns and get matched based on your content style',
        'type': 'sponsor',
    }]


def search_youtube_brandconnect(query, location=''):
    url = 'https://www.youtube.com/intl/ALL_za/brandconnect/'
    return [{
        'title': f'YouTube BrandConnect - {query} Sponsorships', 'company': 'YouTube BrandConnect',
        'location': 'Global', 'source': 'BrandConnect',
        'apply_link': url, 'description': f"YouTube's official platform matching {query} creators with brand sponsorship deals",
        'type': 'sponsor',
    }]


def search_sponsor_directory(query, location=''):
    search_query = urllib.parse.quote(query)
    url = f'https://sponsorgap.com/search?q={search_query}'
    return [{
        'title': f'{query} Sponsors & Brand Deals Directory', 'company': 'SponsorGap',
        'location': location or 'Global', 'source': 'SponsorGap',
        'apply_link': url, 'description': f'Browse brands actively sponsoring {query} content creators and influencers',
        'type': 'sponsor',
    }]
