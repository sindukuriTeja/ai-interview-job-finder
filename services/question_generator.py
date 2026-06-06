import json
import random
from services.ollama_client import OllamaClient

QUESTION_BANK = {
    "python": [
        {"question": "Explain the difference between a list and a tuple in Python. When would you use each?", "difficulty": "easy", "category": "technical"},
        {"question": "How does Python's garbage collector work? Explain reference counting and the generational collector.", "difficulty": "hard", "category": "technical"},
        {"question": "What are decorators in Python and how have you used them in your projects?", "difficulty": "medium", "category": "technical"},
        {"question": "Explain the GIL (Global Interpreter Lock) and its impact on multithreading.", "difficulty": "hard", "category": "technical"},
        {"question": "How would you optimize a Python application that's running slowly?", "difficulty": "medium", "category": "problem_solving"},
    ],
    "javascript": [
        {"question": "Explain the event loop in JavaScript. How does it handle asynchronous operations?", "difficulty": "medium", "category": "technical"},
        {"question": "What is the difference between var, let, and const? When would you use each?", "difficulty": "easy", "category": "technical"},
        {"question": "Explain closures with a practical example from your experience.", "difficulty": "medium", "category": "technical"},
        {"question": "How does prototypal inheritance differ from classical inheritance?", "difficulty": "medium", "category": "technical"},
        {"question": "Describe your approach to handling errors in async/await code.", "difficulty": "medium", "category": "problem_solving"},
    ],
    "react": [
        {"question": "Explain the virtual DOM and how React's reconciliation algorithm works.", "difficulty": "medium", "category": "technical"},
        {"question": "When would you use useEffect vs useMemo vs useCallback?", "difficulty": "medium", "category": "technical"},
        {"question": "How do you manage state in large React applications? Compare different approaches.", "difficulty": "hard", "category": "technical"},
        {"question": "Describe how you would optimize a React component that re-renders too frequently.", "difficulty": "medium", "category": "problem_solving"},
    ],
    "java": [
        {"question": "Explain the difference between abstract classes and interfaces in Java.", "difficulty": "easy", "category": "technical"},
        {"question": "How does Java's garbage collection work? Describe the different GC algorithms.", "difficulty": "hard", "category": "technical"},
        {"question": "What is the Java Memory Model and how does it affect concurrent programming?", "difficulty": "hard", "category": "technical"},
        {"question": "Explain the SOLID principles with examples from your Java projects.", "difficulty": "medium", "category": "technical"},
    ],
    "sql": [
        {"question": "Explain the difference between INNER JOIN, LEFT JOIN, and CROSS JOIN.", "difficulty": "easy", "category": "technical"},
        {"question": "How would you optimize a slow-running SQL query? Walk through your process.", "difficulty": "medium", "category": "problem_solving"},
        {"question": "Explain database indexing strategies and when to use composite indexes.", "difficulty": "medium", "category": "technical"},
        {"question": "What are database transactions and isolation levels? When would you use each level?", "difficulty": "hard", "category": "technical"},
    ],
    "docker": [
        {"question": "Explain the difference between a Docker image and a container.", "difficulty": "easy", "category": "technical"},
        {"question": "How would you optimize a Docker image for production deployment?", "difficulty": "medium", "category": "problem_solving"},
        {"question": "Describe your experience with Docker networking and multi-container setups.", "difficulty": "medium", "category": "technical"},
    ],
    "kubernetes": [
        {"question": "Explain the architecture of a Kubernetes cluster.", "difficulty": "medium", "category": "technical"},
        {"question": "How do you handle rolling deployments and rollbacks in Kubernetes?", "difficulty": "medium", "category": "technical"},
        {"question": "Describe a challenging Kubernetes issue you debugged and how you resolved it.", "difficulty": "hard", "category": "problem_solving"},
    ],
    "machine learning": [
        {"question": "Explain the bias-variance tradeoff and how it affects model selection.", "difficulty": "medium", "category": "technical"},
        {"question": "Walk me through your process for a complete ML project from data to deployment.", "difficulty": "hard", "category": "problem_solving"},
        {"question": "How do you handle imbalanced datasets? Describe techniques you've used.", "difficulty": "medium", "category": "technical"},
        {"question": "Explain overfitting and the strategies you use to prevent it.", "difficulty": "easy", "category": "technical"},
    ],
    "aws": [
        {"question": "Describe the AWS services you've used and how they fit together in your architecture.", "difficulty": "medium", "category": "technical"},
        {"question": "How would you design a highly available and scalable system on AWS?", "difficulty": "hard", "category": "problem_solving"},
        {"question": "Explain the difference between EC2, ECS, and Lambda. When would you use each?", "difficulty": "medium", "category": "technical"},
    ],
    "data science": [
        {"question": "Walk me through your approach to exploratory data analysis on a new dataset.", "difficulty": "medium", "category": "problem_solving"},
        {"question": "How do you validate your statistical findings and avoid common pitfalls?", "difficulty": "hard", "category": "technical"},
        {"question": "Describe a project where your data analysis led to a significant business decision.", "difficulty": "medium", "category": "behavioral"},
    ],
    "leadership": [
        {"question": "Tell me about a time you led a team through a difficult technical challenge.", "difficulty": "medium", "category": "behavioral"},
        {"question": "How do you handle disagreements within your team about technical decisions?", "difficulty": "medium", "category": "behavioral"},
    ],
    "communication": [
        {"question": "Describe a time when you had to explain a complex technical concept to non-technical stakeholders.", "difficulty": "medium", "category": "behavioral"},
        {"question": "How do you ensure effective communication in a remote or distributed team?", "difficulty": "medium", "category": "behavioral"},
    ],
}

GENERAL_QUESTIONS = [
    {"question": "Tell me about yourself and your most recent role.", "difficulty": "easy", "category": "behavioral", "skill_targeted": "general"},
    {"question": "What's the most challenging technical problem you've solved? Walk me through your approach.", "difficulty": "medium", "category": "problem_solving", "skill_targeted": "general"},
    {"question": "Describe a project where you had to learn a new technology quickly. How did you approach it?", "difficulty": "medium", "category": "behavioral", "skill_targeted": "general"},
    {"question": "How do you stay current with new technologies and industry trends?", "difficulty": "easy", "category": "behavioral", "skill_targeted": "general"},
    {"question": "Tell me about a time you received critical feedback. How did you respond?", "difficulty": "medium", "category": "behavioral", "skill_targeted": "general"},
    {"question": "Describe your ideal development workflow and the tools you prefer.", "difficulty": "easy", "category": "situational", "skill_targeted": "general"},
    {"question": "How do you prioritize tasks when you have multiple deadlines?", "difficulty": "medium", "category": "situational", "skill_targeted": "general"},
    {"question": "What would you do if you disagreed with a technical decision made by your manager?", "difficulty": "medium", "category": "situational", "skill_targeted": "general"},
    {"question": "Where do you see yourself professionally in 3-5 years?", "difficulty": "easy", "category": "behavioral", "skill_targeted": "general"},
    {"question": "Do you have any questions for us about the role or company?", "difficulty": "easy", "category": "behavioral", "skill_targeted": "general"},
]


def determine_difficulty_level(experience_years):
    if experience_years <= 2:
        return "junior"
    elif experience_years <= 5:
        return "mid"
    else:
        return "senior"


def _normalize_skill_targeted(value):
    if value is None:
        return 'general'
    if isinstance(value, list):
        return ', '.join(str(item) for item in value if item is not None)
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


def _normalize_question_text(value):
    if value is None:
        return ''
    return str(value).strip()


def generate_questions(resume_data, num_questions=10):
    ollama = OllamaClient()
    questions = []

    if ollama.is_available():
        ollama_count = num_questions // 2
        rule_count = num_questions - ollama_count

        ollama_questions = ollama.generate_questions(resume_data, ollama_count)
        if ollama_questions:
            for q in ollama_questions:
                question_text = _normalize_question_text(q.get("question"))
                if not question_text:
                    continue

                questions.append({
                    "question": question_text,
                    "category": _normalize_question_text(q.get("category")) or "technical",
                    "difficulty": _normalize_question_text(q.get("difficulty")) or "medium",
                    "skill_targeted": _normalize_skill_targeted(q.get("skill_targeted", "general")) or "general",
                    "source": "ollama"
                })

        if not questions:
            rule_count = num_questions
    else:
        rule_count = num_questions

    rule_questions = generate_rule_based(resume_data, rule_count)
    questions.extend(rule_questions)

    if len(questions) < num_questions:
        remaining = num_questions - len(questions)
        general = random.sample(GENERAL_QUESTIONS, min(remaining, len(GENERAL_QUESTIONS)))
        for q in general:
            q_copy = q.copy()
            q_copy["source"] = "rule_based"
            questions.append(q_copy)

    random.shuffle(questions)
    return questions[:num_questions]


def generate_rule_based(resume_data, num_questions):
    skills = resume_data.get('skills', [])
    experience = resume_data.get('experience_years', 0)
    level = determine_difficulty_level(experience)
    questions = []

    difficulty_map = {
        "junior": ["easy", "medium"],
        "mid": ["medium", "hard"],
        "senior": ["medium", "hard"]
    }
    allowed_difficulties = difficulty_map.get(level, ["medium"])

    for skill in skills:
        skill_lower = skill.lower()
        if skill_lower in QUESTION_BANK:
            skill_questions = QUESTION_BANK[skill_lower]
            filtered = [q for q in skill_questions if q["difficulty"] in allowed_difficulties]
            if not filtered:
                filtered = skill_questions

            selected = random.sample(filtered, min(2, len(filtered)))
            for q in selected:
                questions.append({
                    "question": q["question"],
                    "category": q["category"],
                    "difficulty": q["difficulty"],
                    "skill_targeted": skill,
                    "source": "rule_based"
                })

    if len(questions) > num_questions:
        questions = random.sample(questions, num_questions)

    return questions
