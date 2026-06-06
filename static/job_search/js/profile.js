import firebaseConfig from './firebase-config.js';
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js';
import { getAuth, signOut, deleteUser, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js';

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

function setupProfileUI(user) {
    const profilePhoto = document.getElementById('profilePhoto');
    const profileInitialLarge = document.getElementById('profileInitialLarge');
    const displayName = user.displayName || user.email?.split('@')[0] || 'User';

    if (user.photoURL && profilePhoto) {
        profilePhoto.src = user.photoURL;
        profilePhoto.style.display = 'block';
        if (profileInitialLarge) profileInitialLarge.style.display = 'none';
    } else if (profileInitialLarge) {
        profileInitialLarge.textContent = displayName.charAt(0).toUpperCase();
        profileInitialLarge.style.display = 'flex';
    }
}

onAuthStateChanged(auth, (user) => {
    if (user) {
        setupProfileUI(user);
    }
});

fetch('/api/auth/status')
    .then(r => r.json())
    .then(data => {
        if (data.authenticated) {
            setupProfileUI(data.user);
        }
    })
    .catch(() => {});

// Logout
const logoutBtn = document.getElementById('logoutBtn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        try {
            await signOut(auth);
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        } catch (error) {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        }
    });
}

// Delete account
const deleteAccountBtn = document.getElementById('deleteAccountBtn');
if (deleteAccountBtn) {
    deleteAccountBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to delete your account? This action cannot be undone.')) return;
        try {
            const user = auth.currentUser;
            if (user) {
                await deleteUser(user);
            }
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        } catch (error) {
            if (error.code === 'auth/requires-recent-login') {
                alert('For security, please log out and log back in before deleting your account.');
            } else {
                alert('Failed to delete account. Please try again.');
            }
        }
    });
}
