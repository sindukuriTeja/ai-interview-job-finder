let questions = [];
let currentQuestionIndex = 0;
let interviewData = null;
let timerInterval = null;
let timeLeft = 300;
let questionStartTime = null;
let pasteDetected = false;

document.addEventListener('DOMContentLoaded', () => {
    loadInterviewData();

    document.getElementById('submit-answer-btn').addEventListener('click', submitAnswer);
    document.getElementById('skip-btn').addEventListener('click', skipQuestion);
    document.getElementById('end-interview-btn').addEventListener('click', endInterview);

    initAntiCheat();
});


function initAntiCheat() {
    const answerInput = document.getElementById('answer-input');

    // Detect paste events
    answerInput.addEventListener('paste', (e) => {
        pasteDetected = true;
        logViolation('paste_detected', 'Candidate pasted text into answer field', 'medium');
        showPasteWarning();
    });

    // Disable right-click on answer area
    answerInput.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        return false;
    });

    // Detect rapid typing (possible auto-fill)
    let lastKeyTime = 0;
    let rapidKeyCount = 0;
    answerInput.addEventListener('keydown', () => {
        const now = Date.now();
        if (now - lastKeyTime < 20) {
            rapidKeyCount++;
            if (rapidKeyCount > 20) {
                pasteDetected = true;
                logViolation('rapid_input', 'Abnormally fast typing detected', 'low');
                rapidKeyCount = 0;
            }
        } else {
            rapidKeyCount = 0;
        }
        lastKeyTime = now;
    });

    // Prevent developer tools shortcut
    document.addEventListener('keydown', (e) => {
        if (e.key === 'F12' || (e.ctrlKey && e.shiftKey && e.key === 'I')) {
            e.preventDefault();
            logViolation('devtools_attempt', 'Attempted to open developer tools', 'medium');
        }
    });
}


function showPasteWarning() {
    const answerInput = document.getElementById('answer-input');
    const warning = document.createElement('div');
    warning.className = 'text-orange-400 text-xs mt-1 paste-warning';
    warning.textContent = '⚠️ Copy-paste detected. This will be noted in your report.';

    const existing = answerInput.parentNode.querySelector('.paste-warning');
    if (!existing) {
        answerInput.parentNode.insertBefore(warning, answerInput.nextSibling);
    }
}


async function loadInterviewData() {
    const storedData = sessionStorage.getItem(`interview_${INTERVIEW_ID}`);
    if (storedData) {
        interviewData = JSON.parse(storedData);
        questions = interviewData.questions;
        displayQuestion();
        return;
    }

    try {
        const response = await fetch(`/api/results/${INTERVIEW_ID}`);
        const data = await response.json();
        if (data.interview && data.interview.status === 'completed') {
            window.location.href = `/results/${INTERVIEW_ID}`;
            return;
        }
        if (data.interview && data.interview.status === 'terminated') {
            window.location.href = '/';
            return;
        }
    } catch(e) {}

    document.getElementById('question-text').textContent = 'Interview data not found. Please start from the homepage.';
}


function displayQuestion() {
    if (currentQuestionIndex >= questions.length) {
        endInterview();
        return;
    }

    const q = questions[currentQuestionIndex];
    document.getElementById('question-text').textContent = q.question;
    document.getElementById('question-badge').textContent = `Question ${currentQuestionIndex + 1}/${questions.length}`;
    document.getElementById('difficulty-badge').textContent = q.difficulty.charAt(0).toUpperCase() + q.difficulty.slice(1);
    document.getElementById('category-badge').textContent = q.category.charAt(0).toUpperCase() + q.category.slice(1);

    document.getElementById('answer-input').value = '';
    document.getElementById('feedback-card').classList.add('hidden');
    pasteDetected = false;

    // Remove paste warning
    const warning = document.querySelector('.paste-warning');
    if (warning) warning.remove();

    // Update progress
    const progress = (currentQuestionIndex / questions.length) * 100;
    document.getElementById('interview-progress-bar').style.width = `${progress}%`;
    document.getElementById('progress-text').textContent = `${currentQuestionIndex}/${questions.length} answered`;

    questionStartTime = Date.now();
    startTimer();
}


function startTimer() {
    clearInterval(timerInterval);
    timeLeft = 300;
    updateTimerDisplay();

    timerInterval = setInterval(() => {
        timeLeft--;
        updateTimerDisplay();
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            submitAnswer();
        }
    }, 1000);
}


function updateTimerDisplay() {
    const mins = Math.floor(timeLeft / 60);
    const secs = timeLeft % 60;
    const display = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    const timerEl = document.getElementById('question-timer');
    timerEl.textContent = display;

    if (timeLeft <= 60) {
        timerEl.classList.add('text-red-400');
    } else {
        timerEl.classList.remove('text-red-400');
    }
}


async function submitAnswer() {
    const answerText = document.getElementById('answer-input').value.trim();
    const q = questions[currentQuestionIndex];

    const submitBtn = document.getElementById('submit-answer-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Evaluating...';

    const timeTaken = questionStartTime ? Math.round((Date.now() - questionStartTime) / 1000) : 0;

    try {
        const response = await fetch('/submit-answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                interview_id: INTERVIEW_ID,
                question_id: q.id,
                answer_text: answerText,
                time_taken: timeTaken,
                paste_detected: pasteDetected
            })
        });

        const data = await response.json();

        if (data.terminated) {
            alert('Your interview has been terminated due to too many violations.');
            window.location.href = '/';
            return;
        }

        if (data.success) {
            showFeedback(data.scores);
        } else {
            if (data.error) {
                alert(data.error);
            }
            moveToNextQuestion();
        }
    } catch (err) {
        alert('Error submitting answer. Moving to next question.');
        moveToNextQuestion();
    }

    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit Answer';
    clearInterval(timerInterval);
}


function showFeedback(scores) {
    const feedbackCard = document.getElementById('feedback-card');
    feedbackCard.classList.remove('hidden');

    document.getElementById('score-relevance').textContent = scores.relevance + '/10';
    document.getElementById('score-completeness').textContent = scores.completeness + '/10';
    document.getElementById('score-accuracy').textContent = scores.accuracy + '/10';
    document.getElementById('score-communication').textContent = scores.communication + '/10';
    document.getElementById('feedback-text').textContent = scores.feedback || '';

    document.getElementById('next-question-btn').onclick = moveToNextQuestion;
}


function skipQuestion() {
    submitAnswer();
}


function moveToNextQuestion() {
    currentQuestionIndex++;
    if (currentQuestionIndex >= questions.length) {
        endInterview();
    } else {
        displayQuestion();
    }
}


async function endInterview() {
    clearInterval(timerInterval);

    if (typeof stopProctoring === 'function') stopProctoring();
    if (typeof stopRecording === 'function') stopRecording();

    try {
        const response = await fetch(`/complete-interview/${INTERVIEW_ID}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();
        if (data.success) {
            sessionStorage.removeItem(`interview_${INTERVIEW_ID}`);
            window.location.href = data.redirect;
        }
    } catch (err) {
        window.location.href = `/results/${INTERVIEW_ID}`;
    }
}


window.storeInterviewData = function(data) {
    interviewData = data;
    questions = data.questions;
    sessionStorage.setItem(`interview_${data.interview_id}`, JSON.stringify(data));
};
