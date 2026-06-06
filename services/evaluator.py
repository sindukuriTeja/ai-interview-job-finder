from services.ollama_client import OllamaClient


def evaluate_answer(question_text, answer_text, resume_data):
    ollama = OllamaClient()

    resume_context = f"Skills: {', '.join(resume_data.get('skills', []))}. Experience: {resume_data.get('experience_years', 0)} years."

    if ollama.is_available() and answer_text.strip():
        result = ollama.evaluate_answer(question_text, answer_text, resume_context)
        if result:
            return {
                "relevance": min(10, max(1, result.get("relevance", 5))),
                "completeness": min(10, max(1, result.get("completeness", 5))),
                "accuracy": min(10, max(1, result.get("accuracy", 5))),
                "communication": min(10, max(1, result.get("communication", 5))),
                "overall": min(100, max(0, result.get("overall", 50))),
                "feedback": result.get("feedback", "Evaluated by AI."),
                "source": "ollama"
            }

    return rule_based_evaluation(question_text, answer_text)


def rule_based_evaluation(question_text, answer_text):
    if not answer_text or not answer_text.strip():
        return {
            "relevance": 0,
            "completeness": 0,
            "accuracy": 0,
            "communication": 0,
            "overall": 0,
            "feedback": "No answer provided.",
            "source": "rule_based"
        }

    word_count = len(answer_text.split())
    sentence_count = len([s for s in answer_text.split('.') if s.strip()])

    completeness = min(10, max(1, word_count // 10))

    question_keywords = set(question_text.lower().split())
    answer_keywords = set(answer_text.lower().split())
    overlap = len(question_keywords & answer_keywords)
    relevance = min(10, max(1, overlap * 2))

    communication = min(10, max(1, sentence_count * 2))
    if word_count > 20 and sentence_count > 1:
        communication = min(10, communication + 2)

    accuracy = min(10, max(1, (relevance + completeness) // 2))

    overall = int((relevance + completeness + accuracy + communication) * 2.5)
    overall = min(100, max(0, overall))

    feedback_parts = []
    if word_count < 20:
        feedback_parts.append("Consider providing more detailed answers.")
    if relevance < 5:
        feedback_parts.append("Try to address the question more directly.")
    if communication < 5:
        feedback_parts.append("Structure your response with clear sentences.")
    if completeness >= 7 and relevance >= 7:
        feedback_parts.append("Good effort in addressing the question.")

    feedback = " ".join(feedback_parts) if feedback_parts else "Answer recorded for review."

    return {
        "relevance": relevance,
        "completeness": completeness,
        "accuracy": accuracy,
        "communication": communication,
        "overall": overall,
        "feedback": feedback,
        "source": "rule_based"
    }
