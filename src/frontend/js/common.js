const API_BASE = 'http://localhost:8000';

/* ---------- Theme (dark by default, light optional) ---------- */
(function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem('wavelength_theme'); } catch (e) {}
  document.documentElement.dataset.theme = saved === 'light' ? 'light' : 'dark';
})();

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('wavelength_theme', next); } catch (e) {}
}
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.theme-toggle').forEach((btn) => btn.addEventListener('click', toggleTheme));
});

/* ---------- Session token ---------- */
function getToken() { return localStorage.getItem('wavelength_token'); }
function setToken(token) { localStorage.setItem('wavelength_token', token); }
function clearToken() { localStorage.removeItem('wavelength_token'); }

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ---------- Errors ---------- */
// FastAPI sends `detail` as a string for HTTPException, or as a list of
// {msg, loc} objects for 422 validation errors. Turn either into readable text.
function errorMessage(detail, fallback = 'Something went wrong. Try again.') {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d.msg || '').replace(/^Value error,\s*/i, ''))
      .filter(Boolean)
      .map((m) => (/valid email/i.test(m) ? 'Enter a valid email address' : m))
      .join('. ') || fallback;
  }
  return fallback;
}

const NETWORK_ERROR = `Can't reach the server at ${API_BASE}. Make sure the backend is running (uvicorn main:app --reload).`;

async function apiFetch(path, options = {}) {
  try {
    return await fetch(`${API_BASE}${path}`, options);
  } catch (e) {
    throw new Error(NETWORK_ERROR);
  }
}

// Wrapper around fetch() that attaches the Bearer token and redirects
// to login on a 401 (expired/missing session).
async function authFetch(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await apiFetch(path, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.location.href = 'login.html';
    throw new Error('Session expired');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(errorMessage(err.detail, `Server responded ${res.status}`));
  }
  return res.json();
}

function requireAuth() {
  if (!getToken()) window.location.href = 'login.html';
}

/* ---------- Validators (mirror the rules in backend/models.py) ---------- */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
function isValidEmail(email) { return EMAIL_RE.test(email.trim()); }

const EMAIL_TYPOS = {
  'gmial.com': 'gmail.com', 'gmai.com': 'gmail.com', 'gmail.co': 'gmail.com', 'gamil.com': 'gmail.com',
  'gmail.con': 'gmail.com', 'hotmial.com': 'hotmail.com', 'hotmail.con': 'hotmail.com',
  'yaho.com': 'yahoo.com', 'yahoo.con': 'yahoo.com', 'outlok.com': 'outlook.com', 'outlook.con': 'outlook.com',
  'icloud.con': 'icloud.com',
};
function emailTypoFix(email) {
  const [local, domain] = email.trim().toLowerCase().split('@');
  if (!domain || !EMAIL_TYPOS[domain]) return null;
  return `${local}@${EMAIL_TYPOS[domain]}`;
}

function passwordChecks(pw) {
  return {
    length: pw.length >= 8,
    letter: /[A-Za-z]/.test(pw),
    number: /\d/.test(pw),
    // bcrypt only uses the first 72 bytes
    notTooLong: new TextEncoder().encode(pw).length <= 72,
  };
}
function passwordScore(pw) {
  const c = passwordChecks(pw);
  if (!pw) return 0;
  let s = 0;
  if (c.length) s++;
  if (c.letter && c.number) s++;
  if (pw.length >= 12) s++;
  if (/[^A-Za-z0-9]/.test(pw) && /[A-Z]/.test(pw)) s++;
  return Math.max(s, 1);
}
