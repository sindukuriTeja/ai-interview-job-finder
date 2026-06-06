let candidateId = null;

document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFileUpload(files[0]);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
    });

    document.getElementById('start-interview-btn').addEventListener('click', startInterview);
});


async function handleFileUpload(file) {
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!allowedTypes.includes(file.type) && !file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
        alert('Please upload a PDF or DOCX file.');
        return;
    }

    const progressSection = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const fileName = document.getElementById('file-name');
    const uploadStatus = document.getElementById('upload-status');

    progressSection.classList.remove('hidden');
    fileName.textContent = file.name;
    uploadStatus.textContent = 'Uploading...';
    progressBar.style.width = '30%';

    const formData = new FormData();
    formData.append('resume', file);

    try {
        progressBar.style.width = '60%';
        uploadStatus.textContent = 'Parsing resume...';

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            progressBar.style.width = '100%';
            uploadStatus.textContent = 'Complete!';
            uploadStatus.className = 'text-sm text-green-400';
            candidateId = data.candidate_id;
            showResumePreview(data.resume_data);
        } else {
            uploadStatus.textContent = data.error || 'Upload failed';
            uploadStatus.className = 'text-sm text-red-400';
            progressBar.style.width = '0%';
        }
    } catch (err) {
        uploadStatus.textContent = 'Upload failed. Please try again.';
        uploadStatus.className = 'text-sm text-red-400';
        progressBar.style.width = '0%';
    }
}


function showResumePreview(data) {
    const preview = document.getElementById('resume-preview');
    preview.classList.remove('hidden');

    document.getElementById('preview-name').textContent = data.name || 'Unknown';
    document.getElementById('preview-email').textContent = data.email || '';
    document.getElementById('preview-experience').textContent = `${data.experience_years || 0} years`;

    const skillsContainer = document.getElementById('preview-skills');
    skillsContainer.innerHTML = '';
    (data.skills || []).forEach(skill => {
        const tag = document.createElement('span');
        tag.className = 'px-3 py-1 bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 rounded-lg text-sm';
        tag.textContent = skill;
        skillsContainer.appendChild(tag);
    });

    const titlesContainer = document.getElementById('preview-titles');
    titlesContainer.innerHTML = '';
    (data.job_titles || []).forEach(title => {
        const tag = document.createElement('span');
        tag.className = 'px-3 py-1 bg-purple-500/10 text-purple-300 border border-purple-500/20 rounded-lg text-sm';
        tag.textContent = title;
        titlesContainer.appendChild(tag);
    });

    const eduList = document.getElementById('preview-education');
    eduList.innerHTML = '';
    (data.education || []).forEach(edu => {
        const li = document.createElement('li');
        li.textContent = edu;
        li.className = 'text-sm';
        eduList.appendChild(li);
    });

    preview.scrollIntoView({ behavior: 'smooth' });
}


async function startInterview() {
    if (!candidateId) {
        alert('Please upload a resume first.');
        return;
    }

    const btn = document.getElementById('start-interview-btn');
    btn.disabled = true;
    btn.textContent = 'Generating Questions...';
    btn.classList.add('opacity-50');

    try {
        const response = await fetch(`/start-interview/${candidateId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            sessionStorage.setItem(`interview_${data.interview_id}`, JSON.stringify(data));
            window.location.href = `/interview/${data.interview_id}`;
        } else {
            alert(data.error || 'Failed to start interview.');
            btn.disabled = false;
            btn.textContent = 'Start Interview';
            btn.classList.remove('opacity-50');
        }
    } catch (err) {
        alert('Failed to start interview. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Start Interview';
        btn.classList.remove('opacity-50');
    }
}
