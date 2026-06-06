function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 2rem; right: 2rem; z-index: 9999;
        padding: 1rem 1.5rem; border-radius: 12px; font-size: 0.9rem;
        font-weight: 500; color: white; max-width: 400px;
        backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1);
        animation: slideUp 0.3s ease-out;
        background: ${type === 'error' ? 'rgba(239, 68, 68, 0.9)' : 'rgba(16, 185, 129, 0.9)'};
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function setButtonLoading(btn, loading) {
    if (!btn) return;
    const text = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.btn-loader');
    if (text) text.style.display = loading ? 'none' : 'inline-flex';
    if (loader) loader.style.display = loading ? 'inline-flex' : 'none';
    btn.disabled = loading;
}

async function performServerAuth(endpoint, payload) {
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    let data;
    try {
        data = await response.json();
    } catch (err) {
        const text = await response.text();
        throw new Error(text || 'Authentication failed');
    }

    if (!response.ok) {
        throw new Error(data.error || 'Authentication failed');
    }
    return data;
}

function showSocialNotConfigured() {
    showToast('Social login is not configured in this deployment.', 'error');
}

// Login page handlers
const googleLoginBtn = document.getElementById('googleLoginBtn');
const githubLoginBtn = document.getElementById('githubLoginBtn');
const emailLoginForm = document.getElementById('emailLoginForm');

if (googleLoginBtn) {
    googleLoginBtn.addEventListener('click', (e) => {
        e.preventDefault();
        showSocialNotConfigured();
    });
}

if (githubLoginBtn) {
    githubLoginBtn.addEventListener('click', (e) => {
        e.preventDefault();
        showSocialNotConfigured();
    });
}

if (emailLoginForm) {
    emailLoginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const submitBtn = emailLoginForm.querySelector('.auth-submit-btn');

        setButtonLoading(submitBtn, true);
        try {
            await performServerAuth('/api/auth/login', { email, password });
            window.location.href = '/dashboard';
        } catch (error) {
            showToast(error.message || 'Login failed. Please check your credentials.', 'error');
        } finally {
            setButtonLoading(submitBtn, false);
        }
    });
}

// Signup page handlers
const googleSignupBtn = document.getElementById('googleSignupBtn');
const githubSignupBtn = document.getElementById('githubSignupBtn');
const emailSignupForm = document.getElementById('emailSignupForm');

if (googleSignupBtn) {
    googleSignupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        showSocialNotConfigured();
    });
}

if (githubSignupBtn) {
    githubSignupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        showSocialNotConfigured();
    });
}

if (emailSignupForm) {
    emailSignupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const displayName = document.getElementById('displayName').value;
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const submitBtn = emailSignupForm.querySelector('.auth-submit-btn');

        if (password !== confirmPassword) {
            showToast('Passwords do not match.', 'error');
            return;
        }

        if (password.length < 6) {
            showToast('Password must be at least 6 characters.', 'error');
            return;
        }

        setButtonLoading(submitBtn, true);
        try {
            await performServerAuth('/api/auth/signup', { displayName, email, password });
            window.location.href = '/dashboard';
        } catch (error) {
            showToast(error.message || 'Sign up failed. Please try again.', 'error');
        } finally {
            setButtonLoading(submitBtn, false);
        }
    });
}

// Forgot password
const forgotLink = document.querySelector('.forgot-link');
if (forgotLink) {
    forgotLink.addEventListener('click', async (e) => {
        e.preventDefault();
        showToast('Password reset is not configured on this site.', 'error');
    });
}

