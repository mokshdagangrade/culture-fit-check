/* ==========================================================================
   Wavelength app: chat (left) drives the agent loop + drafts (right)
   ========================================================================== */
const INDIA_STATES = new Set(['Maharashtra', 'Delhi', 'Tamil Nadu']); // keep in sync with backend

const STEPS = [
  { emoji: '🧠', label: 'Read brief',    title: 'Reading your brief',     text: 'Picks out what you\u2019re promoting, the mood, and what you want people to do.' },
  { emoji: '🎨', label: 'Learn voice',   title: 'Learning your voice',    text: 'Studies your brand tone and past posts so drafts sound like you, not a robot.' },
  { emoji: '🌦️', label: 'Check weather', title: 'Checking local weather', text: 'Looks up the real weather in each of your states for something timely to say.' },
  { emoji: '📈', label: 'Scan trends',   title: 'Scanning local trends',  text: 'Finds what people in each state are talking about right now.' },
  { emoji: '✍️', label: 'Draft',         title: 'Drafting per state',     text: 'Writes a separate draft for every state, in parallel.' },
  { emoji: '⚖️', label: 'Review',        title: 'Lining up for review',   text: 'Sets the drafts up for your approval. Your thumbs up and down shape the next run.' },
];

let profile = null;
let currentCandidates = {};   // { state: [ {text, context, thumbs} ] }
let selectedTaglines = {};    // { state: text }
let lastBrief = { prompt: '', contentType: 'caption' };
let contentType = 'caption';
let pendingFiles = [];        // [{ name, examples: [] }]
let busy = false;

const $ = (id) => document.getElementById(id);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();
  wireAccountMenu();

  try {
    profile = await authFetch('/me');
  } catch (err) {
    console.error(err);
    addBot(`<p>I couldn\u2019t load your profile. ${escapeHtml(err.message)}</p>`);
    return;
  }
  if (!profile.profile_complete) { window.location.href = 'profile.html?onboarding=1'; return; }

  $('brand-name-display').textContent = profile.business_name;
  $('email-display').textContent = profile.email;
  $('avatar-letter').textContent = (profile.business_name || profile.email || 'W')[0].toUpperCase();

  Loop.build();
  Loop.start();
  renderGhosts();
  logIdle();
  wireComposer();
  wireResults();
  wireEmail();
  greet();
});

/* ---------- Account menu ---------- */
function wireAccountMenu() {
  $('logout-btn').addEventListener('click', () => { clearToken(); window.location.href = 'login.html'; });
  $('profile-icon-btn').addEventListener('click', () => $('profile-dropdown').classList.toggle('open'));
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.profile-menu')) $('profile-dropdown').classList.remove('open');
  });
}

/* ==========================================================================
   Chat
   ========================================================================== */
function addMsg(role, html) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.innerHTML = (role === 'bot' ? '<div class="orb" aria-hidden="true"></div>' : '') + `<div class="bubble">${html}</div>`;
  $('messages').appendChild(el);
  $('messages').scrollTop = $('messages').scrollHeight;
  return el;
}
const addBot = (html) => addMsg('bot', html);
const addUser = (html) => addMsg('user', html);
function addTyping() { return addBot('<span class="typing" aria-label="Working"><i></i><i></i><i></i></span>'); }

const STARTERS = ['Our fall pumpkin spice launch', 'Weekend flash sale', 'A rainy-day promo'];

function greet() {
  const states = profile.states.join(', ');
  const el = addBot(`
    <p>Hey ${escapeHtml(profile.business_name)}! Tell me what you want to post about and I\u2019ll write a draft for each of your states (${escapeHtml(states)}).</p>
    <p>Want it to sound like you? Attach a file of past posts with the paperclip and I\u2019ll learn from it.</p>
    <div class="chips">${STARTERS.map((s) => `<button type="button" class="chip-btn" data-starter="${escapeHtml(s)}">${escapeHtml(s)}</button>`).join('')}</div>`);
  el.querySelectorAll('[data-starter]').forEach((b) => b.addEventListener('click', () => {
    $('prompt').value = b.dataset.starter; autoGrow(); $('prompt').focus();
  }));
}

function autoGrow() {
  const t = $('prompt');
  t.style.height = 'auto';
  t.style.height = Math.min(t.scrollHeight, 160) + 'px';
}

function wireComposer() {
  const prompt = $('prompt');
  prompt.addEventListener('input', autoGrow);
  prompt.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('composer').requestSubmit(); }
  });

  $('content-type').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-type]');
    if (!btn) return;
    contentType = btn.dataset.type;
    $('content-type').querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b === btn));
  });

  $('attach-btn').addEventListener('click', () => $('file-input').click());
  $('file-input').addEventListener('change', async (e) => { await addFiles(e.target.files); e.target.value = ''; });

  const composer = $('composer');
  ['dragenter', 'dragover'].forEach((ev) => composer.addEventListener(ev, (e) => { e.preventDefault(); composer.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach((ev) => composer.addEventListener(ev, (e) => { e.preventDefault(); composer.classList.remove('drag'); }));
  composer.addEventListener('drop', (e) => addFiles(e.dataTransfer.files));

  $('attachments').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-remove]');
    if (!btn) return;
    pendingFiles.splice(Number(btn.dataset.remove), 1);
    renderAttachments();
  });

  composer.addEventListener('submit', onSend);
}

/* ---------- Style-example files ---------- */
async function addFiles(fileList) {
  for (const file of Array.from(fileList || [])) {
    if (!/\.(txt|md|csv)$/i.test(file.name)) {
      addBot(`<p>I can read <b>.txt</b>, <b>.md</b> and <b>.csv</b> files of past posts. <b>${escapeHtml(file.name)}</b> isn\u2019t one of those.</p>`);
      continue;
    }
    if (file.size > 1_000_000) {
      addBot(`<p><b>${escapeHtml(file.name)}</b> is over 1 MB. Try a shorter file with your best posts.</p>`);
      continue;
    }
    const examples = parseExamples(await file.text(), file.name);
    if (!examples.length) {
      addBot(`<p>I couldn\u2019t find any posts in <b>${escapeHtml(file.name)}</b>. Put one post per line, or separate posts with a blank line.</p>`);
      continue;
    }
    pendingFiles.push({ name: file.name, examples });
  }
  renderAttachments();
}

function csvCells(line) {
  const cells = []; let cur = ''; let q = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (q) { if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (c === '"') q = false; else cur += c; }
    else if (c === '"') q = true;
    else if (c === ',') { cells.push(cur); cur = ''; }
    else cur += c;
  }
  cells.push(cur);
  return cells;
}

function parseExamples(raw, name) {
  const text = raw.replace(/\r/g, '').trim();
  if (!text) return [];
  let parts;
  if (/\.csv$/i.test(name)) {
    parts = text.split('\n').map((l) => csvCells(l).sort((a, b) => b.length - a.length)[0] || '');
    if (parts.length && /^(posts?|captions?|text|tagline|taglines|content|message)$/i.test(parts[0].trim())) parts.shift();
  } else if (/\n\s*\n/.test(text)) {
    parts = text.split(/\n\s*\n/);
  } else {
    parts = text.split('\n');
  }
  return parts
    .map((s) => s.trim().replace(/^\s*(?:[-*\u2022]|\d+[.)])\s+/gm, '').replace(/\s*\n\s*/g, ' ').slice(0, 600))
    .filter((s) => s.length >= 3)
    .slice(0, 50);
}

function renderAttachments() {
  $('attachments').innerHTML = pendingFiles.map((f, i) => `
    <span class="attach-chip">${escapeHtml(f.name)} <small>${f.examples.length} post${f.examples.length === 1 ? '' : 's'}</small>
      <button type="button" data-remove="${i}" aria-label="Remove ${escapeHtml(f.name)}">\u00d7</button></span>`).join('');
}

/* ---------- Send ---------- */
async function onSend(e) {
  e.preventDefault();
  if (busy) return;
  const text = $('prompt').value.trim();
  const files = pendingFiles;
  if (!text && !files.length) { $('prompt').focus(); return; }

  busy = true; $('send-btn').disabled = true;
  const fileNote = files.map((f) => `<span class="file-tag">📎 ${escapeHtml(f.name)}</span>`).join(' ');
  addUser(`${text ? `<p>${escapeHtml(text)}</p>` : ''}${fileNote ? `<div>${fileNote}</div>` : ''}`);
  $('prompt').value = ''; autoGrow();
  pendingFiles = []; renderAttachments();

  try {
    if (files.length) await saveExamples(files);
    if (!text) {
        addBot('<p>Got it. What should we post about?</p>');
    } else {
        const typing = addTyping();

        const data = await authFetch('/chat', {
            method: 'POST',
            body: JSON.stringify({
                message: text
            }),
        });

        typing.remove();

        addBot(`<p>${escapeHtml(data.response)}</p>`);
    }
  } catch (err) {
    addBot(`<p>That didn\u2019t work: ${escapeHtml(err.message)}</p>`);
  } finally {
    busy = false; $('send-btn').disabled = false; $('prompt').focus();
  }
}

async function saveExamples(files) {
  const existing = new Set(profile.past_taglines || []);
  const fresh = [...new Set(files.flatMap((f) => f.examples))].filter((x) => !existing.has(x));
  if (!fresh.length) { addBot('<p>I already have all of those posts saved.</p>'); return; }
  profile = await authFetch('/me', { method: 'PUT', body: JSON.stringify({ past_taglines: [...existing, ...fresh] }) });
  addBot(`<p>Saved <b>${fresh.length}</b> style example${fresh.length === 1 ? '' : 's'} from your file${files.length === 1 ? '' : 's'}. You now have ${profile.past_taglines.length} in total.</p>`);
}

/* ==========================================================================
   Agent loop (SVG animation)
   ========================================================================== */
const Loop = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const NX = (i) => 80 + i * 148;
  const NY = (i) => (i % 2 === 0 ? 84 : 174);
  let svg, mainPath, retPath, litMain, litRet, pulse, nodes = [], nodeLen = [], L = 0, R = 0;
  let mode = 'idle';            // idle | run | done
  let cur = 0, target = 0, last = 0, captionIdx = -2, raf = null;

  const el = (name, attrs = {}, parent) => {
    const n = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (parent) parent.appendChild(n);
    return n;
  };

  function build() {
    svg = $('loop');
    svg.innerHTML = '';
    const defs = el('defs', {}, svg);
    const g = el('linearGradient', { id: 'loop-grad', gradientUnits: 'userSpaceOnUse', x1: 60, x2: 840, y1: 0, y2: 0 }, defs);
    [['0', 'var(--blue)'], ['.55', 'var(--violet)'], ['1', 'var(--magenta)']].forEach(([o, c]) => {
      const s = el('stop', { offset: o }, g); s.style.stopColor = c;
    });

    let d = `M ${NX(0)} ${NY(0)}`;
    for (let i = 1; i < STEPS.length; i++) {
      const mid = (NX(i - 1) + NX(i)) / 2;
      d += ` C ${mid} ${NY(i - 1)}, ${mid} ${NY(i)}, ${NX(i)} ${NY(i)}`;
    }
    const last5 = STEPS.length - 1;
    const rd = `M ${NX(last5)} ${NY(last5)} C ${NX(last5) + 12} 272, ${NX(0) - 12} 272, ${NX(0)} ${NY(0)}`;

    mainPath = el('path', { d, class: 'track' }, svg);
    retPath = el('path', { d: rd, class: 'track ret' }, svg);
    L = mainPath.getTotalLength(); R = retPath.getTotalLength();
    litMain = el('path', { d, class: 'lit' }, svg);
    litRet = el('path', { d: rd, class: 'lit' }, svg);
    [litMain, litRet].forEach((p, i) => { const len = i ? R : L; p.style.strokeDasharray = len; p.style.strokeDashoffset = len; });
    const rl = el('text', { x: 450, y: 270, class: 'ret-label' }, svg);
    rl.textContent = 'your 👍 and 👎 shape the next run';

    // node positions along the path (x is monotonic, so scan for it)
    nodeLen = STEPS.map((_, i) => {
      let best = 0, bestDx = Infinity;
      for (let s = 0; s <= L; s += 2) {
        const dx = Math.abs(mainPath.getPointAtLength(s).x - NX(i));
        if (dx < bestDx) { bestDx = dx; best = s; }
      }
      return best;
    });

    nodes = STEPS.map((s, i) => {
      const grp = el('g', { class: 'node', transform: `translate(${NX(i)} ${NY(i)})` }, svg);
      el('circle', { class: 'halo', r: 36 }, grp);
      el('circle', { class: 'disc', r: 27 }, grp);
      el('text', { class: 'emoji' }, grp).textContent = s.emoji;
      const lbl = el('text', { class: 'lbl', y: -44 }, grp);
      lbl.textContent = s.label;
      return grp;
    });

    const glow = el('circle', { class: 'pulse-glow', r: 11 }, svg);
    const core = el('circle', { class: 'pulse-core', r: 5 }, svg);
    pulse = [glow, core];
    place(0);
  }

  function place(s) {
    const onMain = s <= L;
    const p = onMain ? mainPath.getPointAtLength(s) : retPath.getPointAtLength(Math.min(s - L, R));
    pulse.forEach((c) => { c.setAttribute('cx', p.x); c.setAttribute('cy', p.y); });
    const mainDone = Math.min(s, L), retDone = Math.max(0, Math.min(s - L, R));
    litMain.style.strokeDashoffset = L - mainDone;
    litRet.style.strokeDashoffset = R - retDone;
    // a zero-length dash with round caps still paints a dot, so hide until there is real progress
    litMain.style.opacity = mainDone > 1 ? 1 : 0;
    litRet.style.opacity = retDone > 1 ? 1 : 0;
    pulse.forEach((c) => { c.style.opacity = mode === 'done' ? 0 : ''; });
  }

  function setCaption(i) {
    if (i === captionIdx) return;
    captionIdx = i;
    if (i < 0) { $('cap-title').textContent = 'Standing by'; $('cap-text').textContent = 'Every brief goes through the same steps.'; return; }
    if (i >= STEPS.length) { $('cap-title').textContent = 'Learning from feedback'; $('cap-text').textContent = 'Every thumbs up or down you give is saved, so the next run can lean on what worked.'; return; }
    $('cap-title').textContent = STEPS[i].title; $('cap-text').textContent = STEPS[i].text;
  }

  function frame(ts) {
    const dt = Math.min((ts - last) / 1000, 0.1); last = ts;
    if (mode === 'idle') {
      if (!reduceMotion) cur = (cur + dt * ((L + R) / 11)) % (L + R);
      let idx = -1;
      nodeLen.forEach((n, i) => { if (cur >= n - 6) idx = i; });
      if (cur > L) idx = STEPS.length;
      nodes.forEach((n, i) => { n.classList.toggle('active', i === idx && cur <= L); n.classList.remove('done'); });
      setCaption(idx);
    } else {
      cur += (target - cur) * (reduceMotion ? 1 : Math.min(1, dt * 3.4));
    }
    place(cur);
    raf = requestAnimationFrame(frame);
  }

  return {
    build,
    start() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } },
    begin() {
      mode = 'run'; cur = 0; target = 0;
      $('cap-hint').hidden = true;
      nodes.forEach((n) => n.classList.remove('active', 'done', 'error'));
      captionIdx = -2;
      $('stage').classList.remove('compact');
    },
    activate(i) {
      nodes.forEach((n, j) => { n.classList.toggle('active', j === i); if (j < i) n.classList.add('done'); n.classList.remove('error'); });
      target = nodeLen[i];
      setCaption(i);
    },
    complete() {
      nodes.forEach((n) => { n.classList.remove('active'); n.classList.add('done'); });
      target = L; mode = 'done';
      $('stage').classList.add('compact');
    },
    fail(i) {
      nodes[i].classList.remove('active'); nodes[i].classList.add('error');
      mode = 'done';
      $('cap-title').textContent = 'The loop stopped'; $('cap-text').textContent = 'See the run log for what went wrong, then send your brief again.';
    },
    idle() { mode = 'idle'; captionIdx = -2; $('cap-hint').hidden = false; },
  };
})();

function setStatus(state, text) {
  const s = $('status'); s.dataset.s = state; s.textContent = text;
}

/* ---------- Run log ---------- */
let runStart = 0;
function logIdle() {
  $('trace-log').innerHTML = '<div class="tl idle">Waiting for your first brief. Each step of the loop will be logged here.</div>';
}
function log(tag, msg, err = false) {
  const box = $('trace-log');
  if (box.querySelector('.idle')) box.innerHTML = '';
  const t = ((performance.now() - runStart) / 1000).toFixed(1);
  const row = document.createElement('div');
  row.className = 'tl' + (err ? ' err' : '');
  row.innerHTML = `<span class="t">${t}s</span><span class="tag">${escapeHtml(tag)}</span><span class="msg">${escapeHtml(msg)}</span>`;
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;
}

/* ---------- The run ---------- */
async function runLoop({ statesOverride = null, quiet = false } = {}) {
  const { prompt, contentType: ctype } = lastBrief;
  const states = statesOverride || profile.states;
  const typing = quiet ? null : addTyping();

  Loop.begin();
  setStatus('running', 'Running');
  $('trace').open = true;
  $('trace-log').innerHTML = '';
  $('pipeline-note').textContent = '';
  runStart = performance.now();
  renderSkeletons(states);

  // Kick off the real request right away; the animation catches up alongside it.
  const request = authFetch('/generate-taglines', {
    method: 'POST',
    body: JSON.stringify({ prompt, content_type: ctype, states: statesOverride || undefined }),
  });
  request.catch(() => {});

  const step = async (i, tag, msg, ms = 700) => {
    Loop.activate(i); log(tag, msg); await wait(reduceMotion ? 0 : ms);
  };

  let activeStep = 0;
  try {
    activeStep = 0; await step(0, 'brief', `"${prompt.length > 60 ? prompt.slice(0, 60) + '\u2026' : prompt}" as a ${ctype}`);
    activeStep = 1; await step(1, 'voice', `tone: ${profile.tone || 'neutral'}, ${(profile.past_taglines || []).length} saved example${(profile.past_taglines || []).length === 1 ? '' : 's'}`);
    activeStep = 2; await step(2, 'weather', `asking Open-Meteo for ${states.join(', ')}`);
    activeStep = 3; await step(3, 'trends', `looking up trends for ${states.length} state${states.length === 1 ? '' : 's'}`);
    activeStep = 4; Loop.activate(4); log('draft', `writing ${states.length} draft${states.length === 1 ? '' : 's'}`);

    const data = await request;
    data.results.forEach((r) => {
      const c = r.grounding_context || {};
      log('weather', `${r.state}: ${c.weather}`);
    });
    await wait(reduceMotion ? 0 : 400);
    activeStep = 5; await step(5, 'review', `${data.results.length} draft${data.results.length === 1 ? '' : 's'} ready`, 600);

    data.results.forEach((r) => {
      if (statesOverride) {
        currentCandidates[r.state] = [...(currentCandidates[r.state] || []), { text: r.text, context: r.grounding_context, thumbs: null }];
      } else {
        currentCandidates[r.state] = [{ text: r.text, context: r.grounding_context, thumbs: null }];
      }
    });
    if (!statesOverride) selectedTaglines = {};
    renderCards();
    Loop.complete();
    setStatus('done', `${data.results.length} draft${data.results.length === 1 ? '' : 's'} ready`);
    $('pipeline-note').textContent = data.note;
    $('trace').open = false;
    updateEmailVisibility();
    if (typing) typing.remove();
    if (!quiet) addBot(`<p>Done. ${data.results.length} draft${data.results.length === 1 ? ' is' : 's are'} on the right, one per state.</p><p>Give each a \ud83d\udc4d or \ud83d\udc4e, then tap <b>Use this</b> on your favorites and I\u2019ll help you email them.</p>`);
  } catch (err) {
    Loop.fail(activeStep);
    log('error', err.message, true);
    setStatus('error', 'Stopped');
    renderCards();
    if (typing) typing.remove();
    addBot(`<p>The loop stopped at <b>${escapeHtml(STEPS[activeStep].label.toLowerCase())}</b>: ${escapeHtml(err.message)}</p><p>Send your brief again once that\u2019s sorted.</p>`);
  }
}

/* ==========================================================================
   Results
   ========================================================================== */
function renderGhosts() {
  $('results').innerHTML = profile.states.map((s) => `
    <div class="state-card ghost" data-country="${INDIA_STATES.has(s) ? 'India' : 'US'}">
      <div><b>${escapeHtml(s)}</b><br>Your draft lands here</div>
    </div>`).join('');
}
function renderSkeletons(states) {
  const all = statesOverrideSafe(states);
  $('results').innerHTML = all.map((s) => {
    if (currentCandidates[s] && currentCandidates[s].length && states.length < profile.states.length) return cardTemplate(s);
    return `<div class="state-card skeleton" data-country="${INDIA_STATES.has(s) ? 'India' : 'US'}" data-state="${escapeHtml(s)}">
      <div class="skel" style="width:40%;height:20px"></div><div class="skel" style="width:70%"></div>
      <div class="skel"></div><div class="skel" style="width:90%"></div><div class="skel" style="width:55%"></div></div>`;
  }).join('');
}
function statesOverrideSafe(states) { return states.length < profile.states.length ? profile.states : states; }

function renderCards() {
  $('results').innerHTML = profile.states.map((s) =>
    (currentCandidates[s] && currentCandidates[s].length) ? cardTemplate(s)
      : `<div class="state-card ghost" data-country="${INDIA_STATES.has(s) ? 'India' : 'US'}"><div><b>${escapeHtml(s)}</b><br>Nothing drafted yet</div></div>`
  ).join('');
}

function ctxChips(context) {
  if (!context) return '';
  const chips = [];
  if (context.weather) chips.push(`<span title="${escapeHtml(context.weather)}">🌦️ ${escapeHtml(context.weather)}</span>`);
  if (context.trend) {
    const stub = String(context.trend).startsWith('[placeholder');
    chips.push(`<span title="${escapeHtml(context.trend)}">📈 ${stub ? 'Trends not connected yet' : escapeHtml(context.trend)}</span>`);
  }
  return chips.length ? `<div class="ctx">${chips.join('')}</div>` : '';
}

function cardTemplate(state) {
  const candidates = currentCandidates[state] || [];
  const country = INDIA_STATES.has(state) ? 'India' : 'US';
  const latest = candidates[candidates.length - 1];
  return `
    <div class="state-card" data-state="${escapeHtml(state)}" data-country="${country}">
      <div class="state-card-head">
        <span class="state-name">${escapeHtml(state)}</span>
        <button class="regen-btn" type="button" data-action="regen">Regenerate</button>
      </div>
      ${ctxChips(latest && latest.context)}
      <div class="candidate-list">
        ${candidates.map((c, i) => candidateTemplate(state, i, c)).join('')}
      </div>
    </div>`;
}

function candidateTemplate(state, index, c) {
  const isSelected = selectedTaglines[state] === c.text;
  return `
    <div class="candidate-row ${isSelected ? 'selected' : ''}" data-index="${index}">
      <div class="candidate-text">${escapeHtml(c.text)}</div>
      <div class="candidate-actions">
        <button type="button" class="thumb ${c.thumbs === 'up' ? 'active' : ''}" data-action="up" aria-label="Thumbs up" aria-pressed="${c.thumbs === 'up'}">👍</button>
        <button type="button" class="thumb ${c.thumbs === 'down' ? 'active' : ''}" data-action="down" aria-label="Thumbs down" aria-pressed="${c.thumbs === 'down'}">👎</button>
        <button type="button" class="use-btn" data-action="use">${isSelected ? 'Selected' : 'Use this'}</button>
      </div>
    </div>`;
}

function rerenderCard(state) {
  const card = Array.from(document.querySelectorAll('.state-card[data-state]')).find((c) => c.dataset.state === state);
  if (card) card.outerHTML = cardTemplate(state);
}

function wireResults() {
  $('results').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const card = btn.closest('.state-card');
    const state = card.dataset.state;
    if (btn.dataset.action === 'regen') return regenerateState(state);
    const index = Number(btn.closest('.candidate-row').dataset.index);
    if (btn.dataset.action === 'use') return selectTagline(state, index);
    return giveFeedback(state, index, btn.dataset.action);
  });
}

async function regenerateState(state) {
  if (busy) return;
  busy = true;
  try {
    await runLoop({ statesOverride: [state], quiet: true });
  } finally { busy = false; }
}

async function giveFeedback(state, index, thumbs) {
  const candidate = currentCandidates[state][index];
  const toggledOff = candidate.thumbs === thumbs;
  candidate.thumbs = toggledOff ? null : thumbs;
  rerenderCard(state);
  if (toggledOff) return; // nothing to record when un-selecting
  try {
    await authFetch('/feedback', { method: 'POST', body: JSON.stringify({ state, tagline_text: candidate.text, thumbs }) });
  } catch (err) { console.error(err); }
}

function selectTagline(state, index) {
  selectedTaglines[state] = currentCandidates[state][index].text;
  rerenderCard(state);
  updateEmailVisibility(true);
}

/* ---------- Email ---------- */
function updateEmailVisibility(scroll = false) {
  const has = Object.keys(selectedTaglines).length > 0;
  const section = $('email-section');
  const wasHidden = section.hidden;
  section.hidden = !has;
  if (has && wasHidden && scroll) section.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest' });
}

function wireEmail() {
  $('draft-email-btn').addEventListener('click', async () => {
    try {
      const data = await authFetch('/draft-email', { method: 'POST', body: JSON.stringify({ selected_taglines: selectedTaglines }) });
      $('email-subject').value = data.subject;
      $('email-body').value = data.body;
      $('email-draft-note').textContent = data.note;
      $('email-draft-box').hidden = false;
    } catch (err) {
      $('email-draft-note').textContent = err.message;
      $('email-draft-box').hidden = false;
    }
  });

  $('send-email-btn').addEventListener('click', async () => {
    try {
      const data = await authFetch('/send-email', {
        method: 'POST',
        body: JSON.stringify({ subject: $('email-subject').value, body: $('email-body').value, approved: true }),
      });
      $('email-send-note').textContent = data.note;
    } catch (err) {
      $('email-send-note').textContent = err.message;
    }
  });
}
