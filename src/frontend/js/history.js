document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();
  const box = document.getElementById('history');
  box.addEventListener('click', e => {
    const button = e.target.closest('[data-copy-history]');
    const poster = e.target.closest('[data-poster]');
    if (poster) {const entry=poster.closest('.history-entry');downloadCampaignPoster(entry.querySelector('img'),entry.querySelector('.history-copy').textContent,'');}
    if (button) copyContent(button, button.closest('.history-draft').querySelector('.history-copy'));
  });
  try {
    const {entries} = await authFetch('/history' + (new URLSearchParams(location.search).get('project') ? '?project_id=' + encodeURIComponent(new URLSearchParams(location.search).get('project')) : ''));
    box.innerHTML = entries.length ? entries.map(entry => `<details class="history-entry"><summary>${escapeHtml(new Date(entry.created_at).toLocaleString())} · ${escapeHtml(entry.content_type)} · ${escapeHtml(entry.prompt)}</summary><div class="history-copy">${escapeHtml(entry.prompt)}</div>${entry.image && /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(entry.image) ? `<div class="image-preview"><img src="${entry.image}" alt="Generated campaign image" loading="lazy"><a class="btn-ghost" href="${entry.image}" download="campaign-image.jpg">Download image</a><button type="button" class="btn-ghost" data-poster>Download poster with content</button></div>` : ''}${entry.response ? `<div class="history-copy">${renderMarkdown(entry.response)}</div>` : ''}${(entry.results || []).map(result => `<section class="history-draft"><h3>${escapeHtml(result.state)}</h3><div class="history-copy">${renderMarkdown(result.text)}</div><button type="button" class="btn-ghost" data-copy-history>Copy</button></section>`).join('')}</details>`).join('') : '<p>No history yet. Send a brief to create your first drafts.</p>';
  } catch (err) { box.textContent = err.message; }
});
