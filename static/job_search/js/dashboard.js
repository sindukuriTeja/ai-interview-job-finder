import firebaseConfig from './firebase-config.js';
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js';
import { getAuth, signOut, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js';

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

function setupUserUI(user) {
    const welcomeName = document.getElementById('welcomeName');
    const userAvatar = document.getElementById('userAvatar');
    const userInitial = document.getElementById('userInitial');
    const dropdownAvatar = document.getElementById('dropdownAvatar');
    const dropdownName = document.getElementById('dropdownName');
    const dropdownEmail = document.getElementById('dropdownEmail');

    const displayName = user.displayName || user.email?.split('@')[0] || 'User';

    if (welcomeName) welcomeName.textContent = displayName.split(' ')[0];

    if (user.photoURL) {
        if (userAvatar) {
            userAvatar.src = user.photoURL;
            userAvatar.style.display = 'block';
        }
        if (userInitial) userInitial.style.display = 'none';
        if (dropdownAvatar) {
            dropdownAvatar.src = user.photoURL;
            dropdownAvatar.style.display = 'block';
        }
    } else {
        const initial = displayName.charAt(0).toUpperCase();
        if (userInitial) {
            userInitial.textContent = initial;
            userInitial.style.display = 'flex';
        }
        if (userAvatar) userAvatar.style.display = 'none';
        if (dropdownAvatar) dropdownAvatar.style.display = 'none';
    }

    if (dropdownName) dropdownName.textContent = displayName;
    if (dropdownEmail) dropdownEmail.textContent = user.email || '';
}

// User menu dropdown toggle
const userAvatarBtn = document.getElementById('userAvatarBtn');
const userDropdown = document.getElementById('userDropdown');

if (userAvatarBtn && userDropdown) {
    userAvatarBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        userDropdown.classList.toggle('show');
    });

    document.addEventListener('click', (e) => {
        if (!userDropdown.contains(e.target) && !userAvatarBtn.contains(e.target)) {
            userDropdown.classList.remove('show');
        }
    });
}

// Logout
const logoutBtn = document.getElementById('logoutBtn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        try {
            await signOut(auth);
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        } catch (error) {
            console.error('Logout error:', error);
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        }
    });
}

// Auth state listener
onAuthStateChanged(auth, (user) => {
    if (user) {
        setupUserUI(user);
    }
});

// Fallback: use session data from server
fetch('/api/auth/status')
    .then(r => r.json())
    .then(data => {
        if (data.authenticated) {
            setupUserUI(data.user);
        }
    })
    .catch(() => {});
