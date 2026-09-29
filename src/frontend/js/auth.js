document.addEventListener('DOMContentLoaded', () => {
  if (getToken()) { window.location.href = 'app.html'; return; }

  const $ = (id) => document.getElementById(id);
  const tabLogin = $('tab-login'), tabSignup = $('tab-signup');
  const formLogin = $('form-login'), formSignup = $('form-signup');

  const EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  const EYE_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.9 17.9A10.6 10.6 0 0 1 12 19c-6.4 0-10-7-10-7a18 18 0 0 1 4.1-5M9.9 5.2A9.7 9.7 0 0 1 12 5c6.4 0 10 7 10 7a18 18 0 0 1-2.2 3.2M1 1l22 22M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';

  /* ---------- Mode switch ---------- */
  function setMode(mode) {
    const login = mode === 'login';
    tabLogin.setAttribute('aria-pressed', login);
    tabSignup.setAttribute('aria-pressed', !login);
    formLogin.classList.toggle('active', login);
    formSignup.classList.toggle('active', !login);
    $('auth-title').textContent = login ? 'Welcome back' : 'Create your account';
    $('auth-sub').textContent = login
      ? 'Log in to pick up where you left off.'
      : 'Takes a minute. You\u2019ll set up your brand next.';
    document.title = login ? 'Wavelength — Log in' : 'Wavelength — Sign up';
    [$('login-error'), $('signup-error')].forEach((b) => b.classList.remove('show'));
  }
  tabLogin.addEventListener('click', () => setMode('login'));
  tabSignup.addEventListener('click', () => setMode('signup'));

  /* ---------- Show / hide password ---------- */
  document.querySelectorAll('[data-reveal]').forEach((btn) => {
    const input = $(btn.dataset.reveal);
    btn.innerHTML = EYE;
    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = show ? EYE_OFF : EYE;
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
  });

  /* ---------- Field helpers ---------- */
  function setFieldError(input, message, html = false) {
    const field = input.closest('.field');
    const msg = field.querySelector('.field-msg');
    field.classList.toggle('invalid', !!message);
    field.classList.toggle('valid', !message && input.value.length > 0);
    input.setAttribute('aria-invalid', message ? 'true' : 'false');
    if (html) msg.innerHTML = message || ''; else msg.textContent = message || '';
  }
  function showFormError(box, text) { box.textContent = text; box.classList.toggle('show', !!text); }

  function checkEmail(input, { hint = false } = {}) {
    const v = input.value.trim();
    if (!v) { setFieldError(input, 'Enter your email address'); return false; }
    if (!isValidEmail(v)) { setFieldError(input, 'That doesn\u2019t look like an email. Try name@example.com'); return false; }
    const fix = hint ? emailTypoFix(v) : null;
    if (fix) {
      setFieldError(input, `Did you mean <button type="button" data-fix="${escapeHtml(fix)}">${escapeHtml(fix)}</button>?`, true);
      return false;
    }
    setFieldError(input, '');
    return true;
  }
  // one-click typo fix
  document.querySelectorAll('.field-msg').forEach((el) => el.addEventListener('click', (e) => {
    const fix = e.target.dataset && e.target.dataset.fix;
    if (!fix) return;
    const input = el.closest('.field').querySelector('input');
    input.value = fix; checkEmail(input);
  }));

  /* ---------- Log in ---------- */
  const le = $('login-email'), lp = $('login-password');
  le.addEventListener('blur', () => le.value && checkEmail(le));
  le.addEventListener('input', () => le.closest('.field').classList.contains('invalid') && checkEmail(le));
  lp.addEventListener('input', () => lp.value && setFieldError(lp, ''));

  formLogin.addEventListener('submit', async (e) => {
    e.preventDefault();
    showFormError($('login-error'), '');
    const okEmail = checkEmail(le);
    const okPw = !!lp.value;
    if (!okPw) setFieldError(lp, 'Enter your password');
    if (!okEmail || !okPw) { (!okEmail ? le : lp).focus(); return; }
    await submit('/auth/login', { email: le.value.trim(), password: lp.value }, $('login-btn'), 'Log in', $('login-error'));
  });

  /* ---------- Sign up ---------- */
  const se = $('signup-email'), sp = $('signup-password'), sc = $('signup-confirm');
  const meter = $('meter');
  let pwTouched = false;

  function renderRules() {
    const c = passwordChecks(sp.value);
    document.querySelectorAll('#signup-rules li').forEach((li) => li.classList.toggle('ok', c[li.dataset.rule]));
    meter.dataset.score = passwordScore(sp.value);
  }
  function checkPassword() {
    const c = passwordChecks(sp.value);
    if (!sp.value) { setFieldError(sp, 'Choose a password'); return false; }
    if (!c.notTooLong) { setFieldError(sp, 'That password is too long. Keep it under 72 bytes.'); return false; }
    if (!c.length || !c.letter || !c.number) { setFieldError(sp, 'Password needs 8+ characters with a letter and a number'); return false; }
    const local = se.value.split('@')[0].toLowerCase();
    if (local.length >= 4 && sp.value.toLowerCase().includes(local)) { setFieldError(sp, 'Don\u2019t use your email name in your password'); return false; }
    setFieldError(sp, '');
    return true;
  }
  function checkConfirm() {
    if (!sc.value) { setFieldError(sc, 'Re-enter your password'); return false; }
    if (sc.value !== sp.value) { setFieldError(sc, 'Passwords don\u2019t match'); return false; }
    setFieldError(sc, '');
    return true;
  }

  se.addEventListener('blur', () => se.value && checkEmail(se, { hint: true }));
  se.addEventListener('input', () => se.closest('.field').classList.contains('invalid') && checkEmail(se));
  sp.addEventListener('input', () => {
    renderRules();
    if (pwTouched) checkPassword();
    if (sc.value) checkConfirm();
  });
  sp.addEventListener('blur', () => { if (sp.value) { pwTouched = true; checkPassword(); } });
  sc.addEventListener('input', () => sc.value && checkConfirm());
  sc.addEventListener('blur', () => sc.value && checkConfirm());

  formSignup.addEventListener('submit', async (e) => {
    e.preventDefault();
    showFormError($('signup-error'), '');
    pwTouched = true;
    const results = [checkEmail(se, { hint: true }), checkPassword(), checkConfirm()];
    const firstBad = [se, sp, sc][results.indexOf(false)];
    if (firstBad) { firstBad.focus(); return; }
    await submit('/auth/signup', { email: se.value.trim(), password: sp.value }, $('signup-btn'), 'Create account', $('signup-error'), se);
  });

  /* ---------- Talk to the API ---------- */
  async function submit(path, body, btn, label, errorBox, emailInput) {
    btn.disabled = true; btn.textContent = 'One sec\u2026';
    try {
      const res = await apiFetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = errorMessage(data.detail, 'Request failed. Try again.');
        if (res.status === 409 && emailInput) {
          setFieldError(emailInput, 'An account with this email already exists. <button type="button" id="goto-login">Log in instead</button>', true);
          $('goto-login').addEventListener('click', () => { $('login-email').value = emailInput.value; setMode('login'); $('login-password').focus(); });
        } else {
          showFormError(errorBox, msg);
        }
        return;
      }
      setToken(data.token);
      window.location.href = data.profile_complete ? 'app.html' : 'profile.html?onboarding=1';
    } catch (err) {
      showFormError(errorBox, err.message);
    } finally {
      btn.disabled = false; btn.textContent = label;
    }
  }
});
