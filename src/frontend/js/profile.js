document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();
  let logoData = '';
  const logoPreview = document.getElementById('brand-logo-preview');
  function renderLogo() { logoPreview.hidden = !logoData; logoPreview.src = logoData || ''; }
  document.getElementById('brand-logo-file').addEventListener('change', async e => {
    try { if(e.target.files[0]) {logoData=await readLogoFile(e.target.files[0]);renderLogo();} }
    catch(err) {showError(err.message);}
    e.target.value='';
  });
  document.getElementById('remove-brand-logo').onclick = () => {logoData='';renderLogo();};

  const params = new URLSearchParams(window.location.search);
  const isOnboarding = params.get('onboarding') === '1';
  document.getElementById('page-heading').textContent = isOnboarding ? 'Let\u2019s set up your brand' : 'Business settings';
  document.getElementById('save-btn').textContent = isOnboarding ? 'Continue' : 'Save changes';
  document.getElementById('back-link').hidden = isOnboarding;

  const statesContainer = document.getElementById('states-container');
  const availableStates = await authFetch("/regions");
  availableStates.forEach(({ group, states }) => {
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
    logoData=profile.logo_data || '';renderLogo();
    document.getElementById('brand-details').value=JSON.stringify(profile.brand_details || {}, null, 2);
    ['description', 'target_audience', 'products'].forEach(id => document.getElementById(id).value = profile[id] || '');
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

  const presetSelect=document.getElementById('brand-preset');
  const presetApply=document.getElementById('apply-brand-preset');
  const presetStatus=document.getElementById('preset-status');
  let presets=[];
  async function loadPresets() {
    try {
      presets=(await authFetch('/brand-presets')).presets;
      presetSelect.replaceChildren(new Option('Choose a fictional brand', ''));
      presets.forEach(p=>presetSelect.add(new Option(p.label,p.preset_id)));
      presetSelect.disabled=!presets.length;
      if(!presets.length) presetStatus.textContent='No demo brands imported yet. Run the preset import command in README, then refresh this page.';
    } catch(err) {presetStatus.textContent=err.message;presetSelect.replaceChildren(new Option('Demo brands unavailable',''));}
  }
  presetSelect.onchange=()=> {
    const preset=presets.find(p=>p.preset_id===presetSelect.value);
    presetApply.disabled=!preset;
    document.getElementById('preset-preview').hidden=!preset;
    if(!preset)return;
    presetStatus.textContent=preset.summary;
    document.getElementById('preset-json').textContent=JSON.stringify(preset.profile,null,2);
    const briefs=document.getElementById('preset-briefs');briefs.replaceChildren();
    (preset.suggested_test_briefs || []).forEach(text=>{const li=document.createElement('li');li.textContent=text;briefs.appendChild(li);});
  };
  presetApply.onclick=()=> {
    const preset=presets.find(p=>p.preset_id===presetSelect.value);if(!preset)return;
    const profile=preset.profile;
    ['business_name','industry','tone','description','target_audience','products'].forEach(id=>document.getElementById(id).value=profile[id] || '');
    document.getElementById('past_taglines').value=(profile.past_taglines || []).join('\n');
    document.getElementById('brand-details').value=JSON.stringify(profile.brand_details || {},null,2);
    document.querySelectorAll('.state-checkbox input').forEach(input=>{input.checked=(profile.states || []).includes(input.value);});
    logoData='';renderLogo();
    document.querySelectorAll('.field.invalid').forEach(field=>{field.classList.remove('invalid');const msg=field.querySelector('.field-msg');if(msg)msg.textContent='';});
    showError('');presetStatus.textContent=preset.label+' filled in. Review the form and save to use it. The previous account logo has been cleared from this form.';
  };
  loadPresets();

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

    let details;
    try {
      details=JSON.parse(document.getElementById('brand-details').value.trim() || '{}');
      if(!details || typeof details!=='object' || Array.isArray(details)) throw new Error();
    } catch(err) {showError('Detailed brand facts must be a valid JSON object.');document.getElementById('brand-details').focus();return;}
    const values = {
      brand_details: details,
      ...Object.fromEntries(['description', 'target_audience', 'products'].map(id => [id, document.getElementById(id).value.trim()])),
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
        body: JSON.stringify({ ...values, logo_data: logoData, states: selectedStates, past_taglines: pastTaglines }),
      });
      window.location.href = 'projects.html';
    } catch (err) {
      showError(err.message);
      btn.disabled = false;
    }
  });
});
