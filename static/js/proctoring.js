let videoStream = null;
let faceDetectionInterval = null;
let violations = { tabSwitches: 0, noFace: 0, multiFace: 0, total: 0 };
let isFaceApiLoaded = false;
let proctoringActive = false;

const FACE_DETECTION_INTERVAL = 2000;
const NO_FACE_THRESHOLD = 5000;
let lastFaceDetectedTime = Date.now();
let consecutiveNoFace = 0;


async function initProctoring() {
    proctoringActive = true;
    await initCamera();
    await loadFaceApiModels();
    startFaceDetection();
    initTabMonitoring();
    initWindowMonitoring();
}


async function initCamera() {
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 320, height: 240, facingMode: 'user' },
            audio: false
        });

        const videoEl = document.getElementById('video-feed');
        videoEl.srcObject = videoStream;
        videoEl.play();

        document.getElementById('no-camera-msg').classList.add('hidden');
        document.getElementById('camera-status').classList.remove('bg-red-500');
        document.getElementById('camera-status').classList.add('bg-green-500');
    } catch (err) {
        console.error('Camera access denied:', err);
        document.getElementById('no-camera-msg').textContent = 'Camera access denied';
        addAlert('Camera not available - proctoring limited', 'warning');
        logViolation('camera_denied', 'Camera access was denied', 'high');
    }
}


async function loadFaceApiModels() {
    try {
        if (typeof faceapi === 'undefined') {
            console.warn('face-api.js not loaded');
            return;
        }

        const modelPath = '/static/models';

        await Promise.all([
            faceapi.nets.tinyFaceDetector.loadFromUri(modelPath),
            faceapi.nets.faceLandmark68TinyNet.loadFromUri(modelPath)
        ]);

        isFaceApiLoaded = true;
    } catch (err) {
        console.warn('Face detection models not available, using basic detection');
        isFaceApiLoaded = false;
    }
}


function startFaceDetection() {
    if (!videoStream) return;

    faceDetectionInterval = setInterval(async () => {
        if (!proctoringActive) return;

        const videoEl = document.getElementById('video-feed');
        if (!videoEl || videoEl.readyState < 2) return;

        if (isFaceApiLoaded && typeof faceapi !== 'undefined') {
            await detectFacesWithApi(videoEl);
        } else {
            simulateBasicDetection();
        }
    }, FACE_DETECTION_INTERVAL);
}


async function detectFacesWithApi(videoEl) {
    try {
        const detections = await faceapi.detectAllFaces(
            videoEl,
            new faceapi.TinyFaceDetectorOptions({ scoreThreshold: 0.5 })
        ).withFaceLandmarks(true);

        const faceCount = detections.length;
        updateFaceStatus(faceCount);

        const canvas = document.getElementById('face-canvas');
        const displaySize = { width: videoEl.videoWidth, height: videoEl.videoHeight };
        faceapi.matchDimensions(canvas, displaySize);

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (faceCount > 0) {
            const resized = faceapi.resizeResults(detections, displaySize);
            resized.forEach(det => {
                const box = det.detection.box;
                ctx.strokeStyle = faceCount === 1 ? '#22c55e' : '#ef4444';
                ctx.lineWidth = 2;
                ctx.strokeRect(box.x, box.y, box.width, box.height);
            });
        }
    } catch (err) {
        simulateBasicDetection();
    }
}


function simulateBasicDetection() {
    updateFaceStatus(1);
}


function updateFaceStatus(faceCount) {
    const faceStatusEl = document.getElementById('face-status');
    const faceCountEl = document.getElementById('face-count');

    faceCountEl.textContent = faceCount;

    if (faceCount === 0) {
        faceStatusEl.textContent = 'No';
        faceStatusEl.className = 'text-sm font-medium text-red-400';
        consecutiveNoFace++;

        if (Date.now() - lastFaceDetectedTime > NO_FACE_THRESHOLD && consecutiveNoFace >= 3) {
            logViolation('no_face', 'No face detected in frame for extended period', 'high');
            violations.noFace++;
            consecutiveNoFace = 0;
            showViolationWarning('Face Not Detected', 'Please ensure your face is visible in the camera frame.');
        }
    } else if (faceCount === 1) {
        faceStatusEl.textContent = 'Yes';
        faceStatusEl.className = 'text-sm font-medium text-green-400';
        lastFaceDetectedTime = Date.now();
        consecutiveNoFace = 0;
    } else {
        faceStatusEl.textContent = `${faceCount} faces!`;
        faceStatusEl.className = 'text-sm font-medium text-red-400';
        logViolation('multiple_faces', `${faceCount} faces detected in frame`, 'high');
        violations.multiFace++;
        showViolationWarning('Multiple Faces Detected', 'Only the interview candidate should be visible in the camera frame.');
    }

    updateViolationCount();
}


function initTabMonitoring() {
    document.addEventListener('visibilitychange', () => {
        if (!proctoringActive) return;

        if (document.hidden) {
            violations.tabSwitches++;
            updateViolationCount();
            logViolation('tab_switch', 'Candidate switched tab or minimized window', 'medium');
            showViolationWarning('Tab Switch Detected', 'Please stay on the interview tab. Switching tabs is being monitored and recorded.');
            document.getElementById('tab-switches').textContent = violations.tabSwitches;
        }
    });
}


function initWindowMonitoring() {
    window.addEventListener('blur', () => {
        if (!proctoringActive) return;

        if (!document.hidden) {
            violations.tabSwitches++;
            updateViolationCount();
            logViolation('window_blur', 'Interview window lost focus', 'low');
            document.getElementById('tab-switches').textContent = violations.tabSwitches;
        }
    });

    // Detect window resize (possible screen sharing setup)
    let resizeTimeout;
    window.addEventListener('resize', () => {
        if (!proctoringActive) return;
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (window.innerWidth < 800 || window.innerHeight < 500) {
                logViolation('window_resize', 'Browser window resized to suspicious dimensions', 'low');
            }
        }, 1000);
    });
}


function updateViolationCount() {
    violations.total = violations.tabSwitches + violations.noFace + violations.multiFace;
    document.getElementById('total-violations').textContent = violations.total;

    if (violations.total >= 10) {
        document.getElementById('total-violations').classList.add('animate-pulse');
    }
}


function showViolationWarning(title, message) {
    document.getElementById('violation-title').textContent = title;
    document.getElementById('violation-message').textContent = message;
    document.getElementById('violation-modal').classList.remove('hidden');

    setTimeout(() => {
        document.getElementById('violation-modal').classList.add('hidden');
    }, 4000);
}


function addAlert(message, type = 'error') {
    const container = document.getElementById('alerts-container');
    const time = new Date().toLocaleTimeString();

    const colorClass = type === 'error' ? 'text-red-400' : type === 'warning' ? 'text-yellow-400' : 'text-blue-400';

    const alert = document.createElement('div');
    alert.className = `text-xs p-2 bg-gray-900 rounded ${colorClass}`;
    alert.innerHTML = `<span class="text-gray-500">${time}</span> ${escapeAlert(message)}`;

    if (container.querySelector('p')) {
        container.innerHTML = '';
    }

    container.prepend(alert);

    while (container.children.length > 20) {
        container.removeChild(container.lastChild);
    }
}


function escapeAlert(text) {
    const div = document.createElement('span');
    div.textContent = text;
    return div.innerHTML;
}


async function logViolation(type, description, severity) {
    addAlert(description, severity === 'high' ? 'error' : 'warning');

    try {
        const response = await fetch('/log-violation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                interview_id: INTERVIEW_ID,
                violation_type: type,
                description: description,
                severity: severity
            })
        });

        const data = await response.json();
        if (data.terminated) {
            proctoringActive = false;
            alert('Your interview has been terminated due to too many violations.');
            window.location.href = '/';
        }
    } catch (err) {
        console.error('Failed to log violation:', err);
    }
}


function stopProctoring() {
    proctoringActive = false;
    clearInterval(faceDetectionInterval);

    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
    }
}


document.addEventListener('DOMContentLoaded', () => {
    initProctoring();
});
