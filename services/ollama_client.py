import requests
import json
from config import Config


class OllamaClient:
    def __init__(self):
        self.base_url = Config.OLLAMA_BASE_URL
        self.model = Config.OLLAMA_MODEL

    def is_available(self):
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False

    def generate(self, prompt, system_prompt=None, temperature=0.7):
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }
            if system_prompt:
                payload["system"] = system_prompt

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                return response.json().get("response", "")
            return None
        except (requests.ConnectionError, requests.Timeout, json.JSONDecodeError):
            return None

    def generate_questions(self, resume_data, num_questions=5):
        system_prompt = """You are an expert technical interviewer. Generate interview questions based on the candidate's resume.
Return ONLY a JSON array of objects with keys: "question", "category", "difficulty", "skill_targeted".
Categories: technical, behavioral, situational, problem_solving
Difficulty: easy, medium, hard
Do not include any text outside the JSON array."""

        prompt = f"""Based on this candidate's profile, generate {num_questions} interview questions:

Name: {resume_data.get('name', 'Unknown')}
Skills: {', '.join(resume_data.get('skills', []))}
Experience: {resume_data.get('experience_years', 0)} years
Job Titles: {', '.join(resume_data.get('job_titles', []))}
Education: {', '.join(resume_data.get('education', []))}

Generate questions that test their claimed skills and experience level. Mix technical and behavioral questions."""

        response = self.generate(prompt, system_prompt, temperature=0.8)
        if response:
            try:
                start = response.find('[')
                end = response.rfind(']') + 1
                if start != -1 and end > start:
                    return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass
        return None

    def evaluate_answer(self, question, answer, resume_context):
        system_prompt = """You are an expert interview evaluator. Score the candidate's answer.
Return ONLY a JSON object with keys:
- "relevance": score 1-10
- "completeness": score 1-10
- "accuracy": score 1-10
- "communication": score 1-10
- "overall": score 1-100
- "feedback": brief constructive feedback string
Do not include any text outside the JSON object."""

        prompt = f"""Evaluate this interview answer:

Question: {question}
Candidate's Answer: {answer}
Candidate's Background: {resume_context}

Score the answer on relevance, completeness, technical accuracy, and communication quality."""

        response = self.generate(prompt, system_prompt, temperature=0.3)
        if response:
            try:
                start = response.find('{')
                end = response.rfind('}') + 1
                if start != -1 and end > start:
                    return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass
        return None
