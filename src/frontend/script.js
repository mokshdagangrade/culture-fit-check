const API_BASE = 'http://localhost:8000';

function setCountry(country) {
  document.body.setAttribute('data-country', country);
  document.getElementById('btn-us').setAttribute('aria-pressed', String(country === 'US'));
  document.getElementById('btn-india').setAttribute('aria-pressed', String(country === 'India'));
  updateReadoutHint();
}

function updateReadoutHint() {
  const country = document.body.getAttribute('data-country');
  const region = document.getElementById('region').value || '—';
  const city = document.getElementById('city').value;
  document.getElementById('readout-label').textContent =
    `${city ? city + ', ' : ''}${region}, ${country} — not fetched yet`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function generate(evt) {
  evt.preventDefault();
  const btn = document.getElementById('generate-btn');
  const readout = document.getElementById('readout');
  btn.disabled = true;
  btn.textContent = 'Generating…';

  const body = {
    brand_name: document.getElementById('brand_name').value,
    industry: document.getElementById('industry').value,
    tone: document.getElementById('tone').value,
    country: document.body.getAttribute('data-country'),
    region: document.getElementById('region').value,
    city: document.getElementById('city').value || null,
    content_type: document.getElementById('content_type').value,
  };

  try {
    const res = await fetch(`${API_BASE}/generate-caption`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    const data = await res.json();
    renderReadout(body, data.grounding_context);
    renderResults(data.candidates, data.note);
  } catch (err) {
    readout.innerHTML = `<div class="empty">Could not reach the backend at ${API_BASE}.<br>Is it running? Error: ${escapeHtml(err.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate';
  }
  return false;
}

function renderReadout(req, context) {
  const readout = document.getElementById('readout');
  readout.classList.remove('pulsing');
  void readout.offsetWidth; // restart animation
  readout.classList.add('pulsing');

  const label = `${req.city ? req.city + ', ' : ''}${req.region}, ${req.country}`;
  readout.innerHTML = `
    <div class="label">${escapeHtml(label)}</div>
    <dl>
      <dt>weather</dt><dd>${escapeHtml(context.weather || '—')}</dd>
      <dt>trend</dt><dd>${escapeHtml(context.trend || '—')}</dd>
    </dl>
  `;
}

function renderResults(candidates, note) {
  const results = document.getElementById('results');
  const list = document.getElementById('candidates');
  results.style.display = 'block';
  list.innerHTML = '';

  if (!candidates || candidates.length === 0) {
    list.innerHTML = '<div class="empty-state">No candidates returned.</div>';
  } else {
    candidates.forEach((text, i) => {
      const row = document.createElement('div');
      row.className = 'candidate';
      row.innerHTML = `
        <div class="num">${String(i + 1).padStart(2, '0')}</div>
        <div>
          <div class="text">${escapeHtml(text)}</div>
          <button class="copy-btn" type="button">Copy</button>
        </div>
      `;
      row.querySelector('.copy-btn').addEventListener('click', (e) => {
        navigator.clipboard.writeText(text);
        e.target.textContent = 'Copied';
        setTimeout(() => { e.target.textContent = 'Copy'; }, 1500);
      });
      list.appendChild(row);
    });
  }
  document.getElementById('pipeline-note').textContent = note || '';
  results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('region').addEventListener('input', updateReadoutHint);
  document.getElementById('form').addEventListener('submit', generate);
  updateReadoutHint();
});