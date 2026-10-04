document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();
  const box = document.getElementById('history');
  box.addEventListener('click', e => {
    const button = e.target.closest('[data-copy-history]');
    if (button) copyContent(button, button.closest('.history-draft').querySelector('.history-copy'));
  });
  try {
    const {entries} = await authFetch('/history');
    box.innerHTML = entries.length ? entries.map(entry => `<details class="history-entry"><summary>${escapeHtml(new Date(entry.created_at).toLocaleString())} · ${escapeHtml(entry.content_type)} · ${escapeHtml(entry.prompt)}</summary><div class="history-copy">${escapeHtml(entry.prompt)}</div>${entry.response ? `<div class="history-copy">${renderMarkdown(entry.response)}</div>` : ''}${(entry.results || []).map(result => `<section class="history-draft"><h3>${escapeHtml(result.state)}</h3><div class="history-copy">${renderMarkdown(result.text)}</div><button type="button" class="btn-ghost" data-copy-history>Copy</button></section>`).join('')}</details>`).join('') : '<p>No history yet. Send a brief to create your first drafts.</p>';
  } catch (err) { box.textContent = err.message; }
});
