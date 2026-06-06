import re
import os
import pdfplumber
from docx import Document


TECHNICAL_SKILLS = {
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'go', 'rust',
    'swift', 'kotlin', 'php', 'scala', 'r', 'matlab', 'sql', 'html', 'css',
    'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring',
    'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy',
    'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'terraform', 'ansible',
    'git', 'jenkins', 'ci/cd', 'agile', 'scrum', 'rest', 'graphql', 'microservices',
    'mongodb', 'postgresql', 'mysql', 'redis', 'elasticsearch', 'kafka',
    'machine learning', 'deep learning', 'nlp', 'computer vision', 'data science',
    'linux', 'unix', 'bash', 'powershell', 'networking', 'security',
    'react native', 'flutter', 'android', 'ios', 'figma', 'photoshop',
    'tableau', 'power bi', 'excel', 'hadoop', 'spark', 'airflow',
    'fastapi', 'nextjs', 'tailwind', 'bootstrap', 'sass', 'webpack',
    'cypress', 'jest', 'selenium', 'pytest', 'junit',
    'blockchain', 'ethereum', 'solidity', 'web3',
    'devops', 'sre', 'monitoring', 'grafana', 'prometheus'
}

SOFT_SKILLS = {
    'leadership', 'communication', 'teamwork', 'problem solving', 'critical thinking',
    'time management', 'adaptability', 'creativity', 'collaboration', 'mentoring',
    'presentation', 'negotiation', 'conflict resolution', 'decision making',
    'project management', 'strategic planning', 'stakeholder management'
}


def parse_resume(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return parse_pdf(file_path)
    elif ext == '.docx':
        return parse_docx(file_path)
    return None


def parse_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return extract_info(text)


def parse_docx(file_path):
    doc = Document(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return extract_info(text)


def extract_info(text):
    result = {
        'name': extract_name(text),
        'email': extract_email(text),
        'phone': extract_phone(text),
        'skills': extract_skills(text),
        'experience_years': extract_experience_years(text),
        'education': extract_education(text),
        'job_titles': extract_job_titles(text),
        'raw_text': text[:3000]
    }
    return result


def extract_name(text):
    lines = text.strip().split('\n')
    for line in lines[:5]:
        line = line.strip()
        if line and len(line) < 60 and not re.search(r'[@\d]', line):
            words = line.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                return line
    return "Candidate"


def extract_email(text):
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    return match.group(0) if match else ""


def extract_phone(text):
    match = re.search(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,15}', text)
    return match.group(0) if match else ""


def extract_skills(text):
    text_lower = text.lower()
    found_skills = []

    for skill in TECHNICAL_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            found_skills.append(skill)

    for skill in SOFT_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            found_skills.append(skill)

    return found_skills


def extract_experience_years(text):
    patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
        r'experience[:\s]*(\d+)\+?\s*years?',
        r'(\d+)\+?\s*years?\s*(?:in|of|working)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    year_pattern = r'(20\d{2}|19\d{2})'
    years = re.findall(year_pattern, text)
    if len(years) >= 2:
        years = sorted([int(y) for y in years])
        exp = years[-1] - years[0]
        if 0 < exp < 40:
            return exp
    return 0


def extract_education(text):
    education = []
    edu_keywords = [
        r"bachelor'?s?", r"master'?s?", r"ph\.?d\.?", r"b\.?s\.?", r"m\.?s\.?",
        r"b\.?tech", r"m\.?tech", r"mba", r"b\.?e\.?", r"m\.?e\.?",
        r"diploma", r"certificate", r"associate'?s?"
    ]
    lines = text.split('\n')
    for line in lines:
        for keyword in edu_keywords:
            if re.search(keyword, line, re.IGNORECASE):
                clean_line = line.strip()
                if clean_line and len(clean_line) < 200:
                    education.append(clean_line)
                break
    return education[:5]


def extract_job_titles(text):
    titles = []
    title_patterns = [
        r'((?:senior|junior|lead|principal|staff|chief)?\s*(?:software|web|mobile|full.?stack|front.?end|back.?end|devops|data|ml|ai|cloud|platform|site reliability)\s*(?:engineer|developer|architect|scientist|analyst))',
        r'((?:senior|junior|lead|principal)?\s*(?:product|project|program|engineering|technical)\s*manager)',
        r'((?:senior|junior|lead)?\s*(?:designer|consultant|administrator|specialist|coordinator))',
        r'((?:cto|ceo|cfo|vp|director|head)\s*(?:of\s*\w+)?)',
        r'(intern(?:ship)?(?:\s*-\s*\w+)?)',
    ]
    text_lower = text.lower()
    for pattern in title_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            title = match.strip().title()
            if title and title not in titles:
                titles.append(title)
    return titles[:5]
