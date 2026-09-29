// Launch regions -- expand as your team locks in more states (see
// STATE_TO_CITY in trend_retrieval.py, which must stay in sync with this list).
const AVAILABLE_STATES = [
  { group: 'US', states: ['Texas', 'Minnesota', 'Florida'] },
  { group: 'India', states: ['Maharashtra', 'Delhi', 'Tamil Nadu'] },
];

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();

  const params = new URLSearchParams(window.location.search);
  const isOnboarding = params.get('onboarding') === '1';
  document.getElementById('page-heading').textContent = isOnboarding ? 'Let\u2019s set up your brand' : 'Business settings';
  document.getElementById('save-btn').textContent = isOnboarding ? 'Continue' : 'Save changes';
  document.getElementById('back-link').hidden = isOnboarding;

  const statesContainer = document.getElementById('states-container');
  AVAILABLE_STATES.forEach(({ group, states }) => {
    const groupEl = document.createElement('div');
    groupEl.innerHTML = `<div class="state-group-label">${group}</div>`;
    states.forEach((state) => {
      const id = `state-${state.replace(/\s+/g, '-')}`;
      const wrap = document.createElement('label');
      wrap.className = 'state-checkbox';
      wrap.innerHTML = `<input type="checkbox" id="${id}" value="${state}" /> ${state}`;
      groupEl.appendChild(wrap);
    });
    statesContainer.appendChild(groupEl);
  });

  try {
    const profile = await authFetch('/me');
    document.getElementById('business_name').value = profile.business_name || '';
    document.getElementById('industry').value = profile.industry || '';
    document.getElementById('tone').value = profile.tone || '';
    document.getElementById('past_taglines').value = (profile.past_taglines || []).join('\n');
    (profile.states || []).forEach((state) => {
      const el = document.getElementById(`state-${state.replace(/\s+/g, '-')}`);
      if (el) el.checked = true;
    });
  } catch (err) {
    showError(err.message);
  }

  function showError(text) {
    const box = document.getElementById('profile-error');
    box.textContent = text;
    box.classList.toggle('show', !!text);
  }
  function fieldError(id, message) {
    const input = document.getElementById(id);
    const field = input.closest('.field');
    field.classList.toggle('invalid', !!message);
    field.querySelector('.field-msg').textContent = message || '';
    return !message;
  }
  ['business_name', 'industry', 'tone'].forEach((id) => {
    document.getElementById(id).addEventListener('input', () => {
      if (document.getElementById(id).value.trim()) fieldError(id, '');
    });
  });
  statesContainer.addEventListener('change', () => {
    if (document.querySelector('.state-checkbox input:checked')) {
      document.getElementById('states-msg').textContent = '';
      document.querySelector('[data-field="states"]').classList.remove('invalid');
    }
  });

  document.getElementById('profile-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    showError('');

    const values = {
      business_name: document.getElementById('business_name').value.trim(),
      industry: document.getElementById('industry').value.trim(),
      tone: document.getElementById('tone').value.trim(),
    };
    const selectedStates = Array.from(document.querySelectorAll('.state-checkbox input:checked')).map((el) => el.value);

    const checks = [
      fieldError('business_name', values.business_name ? '' : 'Enter your business name'),
      fieldError('industry', values.industry ? '' : 'Enter your industry'),
      fieldError('tone', values.tone ? '' : 'Describe your brand tone in a word or two'),
    ];
    const statesOk = selectedStates.length > 0;
    document.querySelector('[data-field="states"]').classList.toggle('invalid', !statesOk);
    document.getElementById('states-msg').textContent = statesOk ? '' : 'Pick at least one state to promote in';
    if (!checks.every(Boolean) || !statesOk) {
      const firstBad = ['business_name', 'industry', 'tone'][checks.indexOf(false)];
      if (firstBad) document.getElementById(firstBad).focus();
      return;
    }

    const pastTaglines = document.getElementById('past_taglines').value
      .split('\n').map((s) => s.trim()).filter(Boolean);

    const btn = document.getElementById('save-btn');
    btn.disabled = true;
    try {
      await authFetch('/me', {
        method: 'PUT',
        body: JSON.stringify({ ...values, states: selectedStates, past_taglines: pastTaglines }),
      });
      window.location.href = 'app.html';
    } catch (err) {
      showError(err.message);
      btn.disabled = false;
    }
  });
});
