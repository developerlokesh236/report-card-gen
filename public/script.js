const $ = (s) => document.querySelector(s);
let editId = null;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(msg, isErr) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast' + (isErr ? ' err' : '');
  setTimeout(() => t.classList.add('hidden'), 2800);
}

// Subjects ki input rows banana
function makeRows(data = []) {
  const n = parseInt($('#count').value, 10);
  if (!n || n < 1 || n > 15) return toast('Subjects 1 se 15 ke beech likhein.', true);
  const box = $('#rows');
  box.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const s = data[i] || {};
    box.insertAdjacentHTML('beforeend', `
      <div class="row">
        <input class="sname" placeholder="Subject ${i + 1} ka naam" value="${esc(s.name || '')}">
        <input class="smarks" type="number" min="0" placeholder="Marks mile" value="${s.marks ?? ''}">
        <input class="smax" type="number" min="1" placeholder="Total marks" value="${s.max || 100}">
      </div>`);
  }
  $('#saveBtn').classList.remove('hidden');
}

function resetForm() {
  editId = null;
  ['studentName', 'rollNo', 'className', 'count'].forEach((id) => ($('#' + id).value = ''));
  $('#rows').innerHTML = '';
  $('#saveBtn').classList.add('hidden');
  $('#cancelBtn').classList.add('hidden');
  $('#saveBtn').textContent = 'Report card banao';
  $('#formTitle').textContent = 'Naya report card';
}

async function save() {
  const subjects = [...document.querySelectorAll('.row')].map((r) => ({
    name: r.querySelector('.sname').value,
    marks: r.querySelector('.smarks').value,
    max: r.querySelector('.smax').value,
  }));
  const body = {
    studentName: $('#studentName').value,
    rollNo: $('#rollNo').value,
    className: $('#className').value,
    subjects,
  };
  const res = await fetch(editId ? `/api/reports/${editId}` : '/api/reports', {
    method: editId ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) return toast(data.error, true);
  toast(editId ? 'Report card update ho gaya.' : 'Report card ban gaya.');
  resetForm();
  await loadList();
  openView(data.id);
}

async function loadList() {
  const list = await (await fetch('/api/reports')).json();
  const box = $('#list');
  if (!list.length) {
    box.innerHTML = '<p class="empty">Abhi koi report card nahi hai. Upar form bharke pehla banayein.</p>';
    return;
  }
  box.innerHTML = list.slice().reverse().map((r) => `
    <div class="item">
      <div>
        <strong>${esc(r.studentName)}</strong><span class="tag ${r.result}">${r.result}</span><br>
        <small>Roll ${esc(r.rollNo || '-')} | Class ${esc(r.className || '-')} | ${r.total}/${r.maxTotal} | ${r.percentage}%</small>
      </div>
      <div class="btns">
        <button class="btn sm" data-a="view" data-id="${r.id}">Dekho</button>
        <button class="btn sm" data-a="edit" data-id="${r.id}">Edit</button>
        <button class="btn sm" data-a="dl" data-id="${r.id}">Download</button>
        <button class="btn sm red" data-a="del" data-id="${r.id}">Delete</button>
      </div>
    </div>`).join('');
}

function openView(id) {
  $('#frame').src = `/api/reports/${id}/view`;
  $('#modal').classList.remove('hidden');
}

async function startEdit(id) {
  const list = await (await fetch('/api/reports')).json();
  const r = list.find((x) => x.id === id);
  if (!r) return;
  editId = id;
  $('#studentName').value = r.studentName;
  $('#rollNo').value = r.rollNo;
  $('#className').value = r.className;
  $('#count').value = r.subjects.length;
  makeRows(r.subjects);
  $('#saveBtn').textContent = 'Changes save karo';
  $('#cancelBtn').classList.remove('hidden');
  $('#formTitle').textContent = 'Report card edit karo';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

$('#list').addEventListener('click', async (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  const id = b.dataset.id;
  if (b.dataset.a === 'view') openView(id);
  if (b.dataset.a === 'edit') startEdit(id);
  if (b.dataset.a === 'dl') window.location = `/api/reports/${id}/download`;
  if (b.dataset.a === 'del') {
    if (!confirm('Ye report card delete karna hai?')) return;
    await fetch(`/api/reports/${id}`, { method: 'DELETE' });
    toast('Report card delete ho gaya.');
    if (editId === id) resetForm();
    loadList();
  }
});

$('#makeRows').addEventListener('click', () => makeRows());
$('#saveBtn').addEventListener('click', save);
$('#cancelBtn').addEventListener('click', resetForm);
$('#closeBtn').addEventListener('click', () => $('#modal').classList.add('hidden'));
$('#printBtn').addEventListener('click', () => $('#frame').contentWindow.print());

loadList();
