const state = {
  user: null,
  routines: [],
  tasks: [],
  history: []
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const api = async (url, options = {}) => {
  const res = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  });
  if (!res.ok) {
    let message = 'Error de operación.';
    try {
      const payload = await res.json();
      message = payload.detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  return res.json();
};

function toast(message) {
  const box = $('#toast');
  box.textContent = message;
  box.classList.add('show');
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => box.classList.remove('show'), 3200);
}

function formatDateTimeLocal(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return {
    date: `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`,
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}`,
    iso: date.toISOString()
  };
}

function storageKey(id, type = 'checked') {
  const user = state.user?.id || 'guest';
  return `checklist-hogar:${user}:${type}:${id}`;
}

function saveLocalTask(input) {
  localStorage.setItem(storageKey(input.id), input.checked ? '1' : '0');
  updateProgress();
}

function saveLocalNote(input) {
  localStorage.setItem(storageKey(input.dataset.taskId, 'note'), input.value || '');
}

function getCheckedTaskIds() {
  return $$('input[data-task]').filter((box) => box.checked).map((box) => box.id);
}

function getNotesByTask() {
  const notes = {};
  $$('.note-input').forEach((input) => {
    if (input.value.trim()) notes[input.dataset.taskId] = input.value.trim();
  });
  return notes;
}

function updateProgress() {
  const boxes = $$('input[data-task]');
  const done = boxes.filter((box) => box.checked).length;
  const total = boxes.length;
  const percent = total ? Math.round((done / total) * 100) : 0;
  $('#doneCount').textContent = done;
  $('#totalCount').textContent = total;
  $('#percentDone').textContent = `${percent}%`;
}

function renderChecklist() {
  const container = $('#routineContainer');
  const search = ($('#taskSearch')?.value || '').trim().toLowerCase();
  container.innerHTML = '';
  state.tasks = [];

  state.routines.forEach((routine) => {
    const visibleTasks = routine.tasks.filter((task) => {
      if (!search) return true;
      return `${routine.title} ${task.title} ${task.zone}`.toLowerCase().includes(search);
    });
    if (!visibleTasks.length) return;

    const card = document.createElement('article');
    card.className = 'routine-card reveal visible';
    card.id = `routine-${routine.id}`;
    card.innerHTML = `
      <div class="section-head">
        <div class="text">
          <span class="eyebrow">${routine.frequency}</span>
          <h3>${routine.title}</h3>
          <p>${routine.description}</p>
        </div>
        <span class="routine-badge">${visibleTasks.length} tareas</span>
      </div>
      <div class="task-list"></div>
    `;

    const list = card.querySelector('.task-list');
    visibleTasks.forEach((task) => {
      state.tasks.push({ ...task, routine_title: routine.title });
      const label = document.createElement('label');
      label.className = 'task-row';
      label.setAttribute('for', task.id);
      label.innerHTML = `
        <input type="checkbox" id="${task.id}" data-task data-routine-id="${routine.id}">
        <span class="checkmark" aria-hidden="true"></span>
        <span class="task-main"><strong>${task.title}</strong><small>${task.zone}</small></span>
        <input class="note-input" type="text" data-task-id="${task.id}" placeholder="Nota">
      `;
      list.appendChild(label);
      const check = label.querySelector('input[type="checkbox"]');
      const note = label.querySelector('.note-input');
      check.checked = localStorage.getItem(storageKey(task.id)) === '1';
      note.value = localStorage.getItem(storageKey(task.id, 'note')) || '';
      check.addEventListener('change', () => saveLocalTask(check));
      note.addEventListener('input', () => saveLocalNote(note));
    });

    container.appendChild(card);
  });
  updateProgress();
}

async function loadChecklist() {
  const data = await api('/api/checklist');
  state.routines = data.routines;
  $('#routineCount').textContent = state.routines.length;
  $('#userLabel').textContent = data.user.name;
  renderChecklist();
  fillRoutineSelect();
}

function fillRoutineSelect() {
  const select = $('#closeRoutine');
  select.innerHTML = '<option value="all">Todas las tareas marcadas</option>';
  state.routines.forEach((routine) => {
    const option = document.createElement('option');
    option.value = routine.id;
    option.textContent = routine.title;
    select.appendChild(option);
  });
}

function openCloseModal() {
  const checked = getCheckedTaskIds();
  if (!checked.length) {
    toast('Marcá al menos una tarea antes de cerrar la rutina.');
    return;
  }
  const dt = formatDateTimeLocal();
  $('#closeDate').value = dt.date;
  $('#closeTime').value = dt.time;
  $('#closeResponsible').value = state.user?.name || '';
  $('#closeObservations').value = '';
  $('#includePending').checked = true;
  updateClosePreview();
  $('#closeRunModal').showModal();
}

function updateClosePreview() {
  const selected = $('#closeRoutine').value;
  const checked = getCheckedTaskIds();
  let scopeTasks = state.tasks;
  if (selected !== 'all') scopeTasks = state.tasks.filter((task) => task.routine_id === selected);
  const completed = scopeTasks.filter((task) => checked.includes(task.id));
  const pending = scopeTasks.length - completed.length;
  const percent = scopeTasks.length ? Math.round((completed.length / scopeTasks.length) * 100) : 0;
  $('#closePreview').innerHTML = `
    <strong>Resumen:</strong> ${completed.length} de ${scopeTasks.length} tareas marcadas · ${percent}% de cumplimiento.
    ${pending > 0 ? `<br><small>${pending} tareas quedarán como pendientes si activás la opción de incluir pendientes.</small>` : ''}
  `;
}

async function closeRoutine(event) {
  event.preventDefault();
  const dt = formatDateTimeLocal();
  const payload = {
    routine_id: $('#closeRoutine').value,
    responsible: $('#closeResponsible').value.trim(),
    observations: $('#closeObservations').value.trim(),
    completed_task_ids: getCheckedTaskIds(),
    notes_by_task: getNotesByTask(),
    include_pending: $('#includePending').checked,
    client_closed_at: `${$('#closeDate').value} ${$('#closeTime').value}` || `${dt.date} ${dt.time}`
  };
  if (!payload.responsible) {
    toast('Indicá el responsable del cierre.');
    return;
  }
  try {
    const result = await api('/api/runs', { method: 'POST', body: JSON.stringify(payload) });
    $('#closeRunModal').close();
    toast('Cierre guardado correctamente.');
    await loadHistory();
    window.open(`/api/runs/${result.run_id}/receipt`, '_blank');
  } catch (error) {
    toast(error.message);
  }
}

async function loadHistory() {
  const data = await api('/api/runs?limit=50');
  state.history = data.runs;
  $('#historyCount').textContent = state.history.length;
  const list = $('#historyList');
  if (!state.history.length) {
    list.innerHTML = '<div class="history-item"><div><h3>Sin cierres registrados</h3><p>Cuando cierres una rutina aparecerá en este historial.</p></div></div>';
    return;
  }
  list.innerHTML = state.history.map((run) => `
    <article class="history-item">
      <div>
        <h3>${run.routine_title} · ${run.percent}%</h3>
        <p>${run.client_closed_at || run.server_closed_at} · Responsable: ${run.responsible} · ${run.completed_count}/${run.total_count} tareas · Usuario: ${run.user_name}</p>
      </div>
      <div class="item-actions">
        <a href="/api/runs/${run.id}/receipt" target="_blank" rel="noopener">Comprobante</a>
        <a href="/api/runs/${run.id}/export.csv">CSV</a>
        <a href="/api/runs/${run.id}/export.json">JSON</a>
        <button type="button" data-delete-run="${run.id}">Borrar</button>
      </div>
    </article>
  `).join('');
  $$('[data-delete-run]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (!confirm('¿Borrar este cierre del historial?')) return;
      await api(`/api/runs/${button.dataset.deleteRun}`, { method: 'DELETE' });
      toast('Cierre borrado.');
      loadHistory();
    });
  });
}

async function loadUsers() {
  if (state.user?.role !== 'admin') return;
  try {
    const data = await api('/api/users');
    const list = $('#usersList');
    list.innerHTML = data.users.map((user) => `
      <article class="user-item">
        <div><h3>${user.name}</h3><p>${user.email} · ${user.role} · ${user.is_active ? 'Activo' : 'Inactivo'}</p></div>
      </article>
    `).join('');
  } catch (_) {}
}

async function createUser(event) {
  event.preventDefault();
  const payload = {
    name: $('#newUserName').value.trim(),
    email: $('#newUserEmail').value.trim(),
    password: $('#newUserPassword').value,
    role: $('#newUserRole').value
  };
  try {
    await api('/api/users', { method: 'POST', body: JSON.stringify(payload) });
    event.target.reset();
    toast('Usuario creado.');
    loadUsers();
  } catch (error) {
    toast(error.message);
  }
}

function clearChecks() {
  if (!confirm('¿Limpiar checks y notas locales? El historial guardado no se modifica.')) return;
  $$('input[data-task]').forEach((box) => {
    box.checked = false;
    localStorage.removeItem(storageKey(box.id));
  });
  $$('.note-input').forEach((input) => {
    input.value = '';
    localStorage.removeItem(storageKey(input.dataset.taskId, 'note'));
  });
  updateProgress();
  toast('Checks y notas locales limpiados.');
}

async function login(event) {
  event.preventDefault();
  $('#loginError').textContent = '';
  try {
    const result = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: $('#loginEmail').value, password: $('#loginPassword').value })
    });
    state.user = result.user;
    showApp();
  } catch (error) {
    $('#loginError').textContent = error.message;
  }
}

async function logout() {
  await api('/api/auth/logout', { method: 'POST', body: '{}' });
  location.reload();
}

function showLogin() {
  $('#loginScreen').hidden = false;
  $('#appShell').hidden = true;
}

async function showApp() {
  $('#loginScreen').hidden = true;
  $('#appShell').hidden = false;
  $('#usersNav').hidden = state.user.role !== 'admin';
  $('#usuarios').hidden = state.user.role !== 'admin';
  await loadChecklist();
  await loadHistory();
  await loadUsers();
}

async function init() {
  $('#loginForm').addEventListener('submit', login);
  $('#logoutBtn').addEventListener('click', logout);
  $('#taskSearch').addEventListener('input', renderChecklist);
  $('#closeRunTop').addEventListener('click', openCloseModal);
  $('#closeRunToolbar').addEventListener('click', openCloseModal);
  $('#closeRunMobile').addEventListener('click', openCloseModal);
  $('#closeRunFloat').addEventListener('click', openCloseModal);
  $('#clearChecksBtn').addEventListener('click', clearChecks);
  $('#clearChecksFloat').addEventListener('click', clearChecks);
  $('#printListsBtn').addEventListener('click', () => window.print());
  $('#reloadHistoryBtn').addEventListener('click', loadHistory);
  $('#closeModalBtn').addEventListener('click', () => $('#closeRunModal').close());
  $('#cancelCloseBtn').addEventListener('click', () => $('#closeRunModal').close());
  $('#closeRoutine').addEventListener('change', updateClosePreview);
  $('#includePending').addEventListener('change', updateClosePreview);
  $('#closeRunForm').addEventListener('submit', closeRoutine);
  $('#userForm').addEventListener('submit', createUser);

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.classList.add('visible');
    });
  }, { threshold: 0.12 });
  $$('.reveal').forEach((el) => observer.observe(el));

  try {
    const data = await api('/api/users/me');
    state.user = data.user;
    await showApp();
  } catch (_) {
    showLogin();
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/service-worker.js').catch(() => {});
  }
}

document.addEventListener('DOMContentLoaded', init);
