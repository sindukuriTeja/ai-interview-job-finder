let mediaRecorder = null;
let audioRecorder = null;
let screenRecorder = null;
let recordedChunks = [];
let audioChunks = [];
let isRecordingAudio = false;


async function initScreenRecording() {
    try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: { cursor: 'always' },
            audio: false
        });

        screenRecorder = new MediaRecorder(screenStream, {
            mimeType: 'video/webm;codecs=vp9'
        });

        screenRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };

        screenRecorder.start(5000); // Record in 5-second chunks
        return true;
    } catch (err) {
        console.warn('Screen recording not available:', err);
        return false;
    }
}


function initAudioRecording() {
    const recordBtn = document.getElementById('audio-record-btn');
    const indicator = document.getElementById('recording-indicator');

    recordBtn.addEventListener('click', async () => {
        if (isRecordingAudio) {
            stopAudioRecording();
            recordBtn.innerHTML = `
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                </svg>
                <span>Record Audio</span>
            `;
            indicator.classList.add('hidden');
        } else {
            await startAudioRecording();
            recordBtn.innerHTML = `
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="2"/>
                </svg>
                <span>Stop Recording</span>
            `;
            recordBtn.classList.remove('bg-red-600/20', 'text-red-400');
            recordBtn.classList.add('bg-red-600', 'text-white');
            indicator.classList.remove('hidden');
        }
    });
}


async function startAudioRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioRecorder = new MediaRecorder(stream);
        audioChunks = [];

        audioRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        audioRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const audioUrl = URL.createObjectURL(audioBlob);
            // Store reference for answer submission
            window.lastAudioRecording = audioBlob;
        };

        audioRecorder.start();
        isRecordingAudio = true;
    } catch (err) {
        console.error('Audio recording failed:', err);
        alert('Could not access microphone.');
    }
}


function stopAudioRecording() {
    if (audioRecorder && audioRecorder.state === 'recording') {
        audioRecorder.stop();
        audioRecorder.stream.getTracks().forEach(track => track.stop());
    }
    isRecordingAudio = false;
}


function stopRecording() {
    stopAudioRecording();

    if (screenRecorder && screenRecorder.state === 'recording') {
        screenRecorder.stop();
        screenRecorder.stream.getTracks().forEach(track => track.stop());
    }
}


function getScreenRecordingBlob() {
    if (recordedChunks.length > 0) {
        return new Blob(recordedChunks, { type: 'video/webm' });
    }
    return null;
}


// Init audio recording controls
document.addEventListener('DOMContentLoaded', () => {
    initAudioRecording();
    // Screen recording is optional - init if user grants permission
    // initScreenRecording(); // Uncomment to auto-start screen recording
});
