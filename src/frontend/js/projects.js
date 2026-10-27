requireAuth();
let projects = [];
const byId = id => document.getElementById(id);
const fileData = file => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve({name: file.name, type: file.type, size: file.size, data: reader.result});
  reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
  reader.readAsDataURL(file);
});
function downloadProjectFile(file) {
  const a = document.createElement('a');
  const blob = !file.data ? URL.createObjectURL(new Blob([file.text || ''], {type: 'text/plain'})) : null;
  if (!blob && !/^data:[^,]*;base64,/.test(file.data)) return;
  a.href = blob || file.data; a.download = file.name; a.click();
  if (blob) setTimeout(() => URL.revokeObjectURL(blob), 1000);
}
function libraryFiles(project) {
  const state = project.state || {};
  return [...(project.files || []), ...(state.files || []), ...(state.generated || []).map((item, i) => ({name: `${item.state || 'Draft'}-${i + 1}.txt`, text: item.text, label: item.approved ? 'Selected' : item.thumbs === 'up' ? 'Liked' : 'Draft'})), ...(state.email?.subject ? [{name:'Email-draft.txt',text:state.email.subject+'\n\n'+state.email.body,label:state.email.approved ? 'Approved' : 'Email draft'}] : [])];
}
function renderProjects() {
  byId('projects-grid').innerHTML = projects.map(p => {
    const files = libraryFiles(p), saved = (p.state?.generated || []).filter(x => x.approved || x.thumbs === 'up').length;
    return `<article class="project-card"><div class="project-card-top"><span class="project-symbol">↗</span><span class="project-eyebrow">${escapeHtml(new Date(p.updated_at).toLocaleDateString())}</span></div><h2><a href="app.html?project=${encodeURIComponent(p.id)}">${escapeHtml(p.name)}</a></h2><p>${files.length} files & drafts · ${saved} liked or selected</p><div class="project-members">${p.members.map(m => `<span class="member-bubble" title="${escapeHtml(m)}">${escapeHtml(m[0].toUpperCase())}</span>`).join('')}<span class="project-eyebrow">${p.members.length === 1 ? 'Just you' : `${p.members.length} members`}</span></div><div class="project-card-footer"><button class="btn-ghost" data-library="${p.id}">View library</button><a href="app.html?project=${encodeURIComponent(p.id)}">Open project →</a></div></article>`;
  }).join('') + `<button type="button" class="project-card new-project-card" id="empty-create"><span>＋</span><h2>Create a project</h2><p>Bring your next campaign to life.</p></button>`;
  byId('empty-create').onclick = () => byId('new-dialog').showModal();
}
byId('new-project').onclick = () => byId('new-dialog').showModal();
byId('close-dialog').onclick = () => byId('new-dialog').close();
byId('close-library').onclick = () => byId('library-dialog').close();
byId('logout').onclick = () => {clearToken(); location.href='login.html';};
byId('project-files').onchange = e => {byId('file-list').textContent = Array.from(e.target.files).map(f => f.name).join(', ');};
byId('projects-grid').onclick = e => {
  const button = e.target.closest('[data-library]'); if (!button) return;
  const project = projects.find(p => p.id === button.dataset.library);
  byId('library-title').textContent = project.name;
  const files = libraryFiles(project);
  byId('library-items').innerHTML = files.length ? files.map((f,i) => `<div class="library-row"><div><strong>${escapeHtml(f.name)}</strong><small>${escapeHtml(f.label || 'Uploaded file')}</small></div><button class="btn-ghost" data-download="${i}">Download</button></div>`).join('') : '<p>No files yet. Upload references or generate your first drafts in chat.</p>';
  byId('library-items').onclick = e => {const b=e.target.closest('[data-download]');if(b) downloadProjectFile(files[Number(b.dataset.download)]);};
  byId('library-dialog').showModal();
};
byId('new-form').onsubmit = async e => {
  e.preventDefault(); const button=byId('create-project');button.disabled=true; byId('create-error').textContent='';
  try {
    const name=byId('project-name').value.trim(); if(!name) throw new Error('Enter a project name.');
    const files=Array.from(byId('project-files').files);
    if(files.reduce((n,f)=>n+f.size,0)>6_000_000) throw new Error('Please keep files under 6 MB total.');
    const project=await authFetch('/projects',{method:'POST',body:JSON.stringify({name,files:await Promise.all(files.map(fileData))})});
    location.href=`app.html?project=${encodeURIComponent(project.id)}`;
  } catch(err) {byId('create-error').textContent=err.message;button.disabled=false;}
};
(async () => {try { const profile=await authFetch('/me');if(!profile.profile_complete){location.href='profile.html?onboarding=1';return;} projects=(await authFetch('/projects')).projects;renderProjects(); const library=new URLSearchParams(location.search).get('library');if(library) document.querySelector(`[data-library="${CSS.escape(library)}"]`)?.click(); }catch(err){byId('projects-grid').textContent='';byId('projects-error').textContent=err.message;}})();
