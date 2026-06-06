const VIEW_META = {
  home: { eyebrow: 'Inicio', title: 'Resumen operativo' },
  checklist: { eyebrow: 'Checklist', title: 'Rutinas por seccion' },
  close: { eyebrow: 'Cerrar rutina', title: 'Comprobante por seccion' },
  history: { eyebrow: 'Historial', title: 'Cierres guardados' },
  calendar: { eyebrow: 'Calendario', title: 'Actividad mensual' },
  admin: { eyebrow: 'Administracion', title: 'Gestion del checklist' }
};

const state = {
  user: null,
  routines: [],
  history: [],
  users: [],
  adminItems: [],
  calendarDate: new Date(),
  selectedCalendarDate: null,
  calendarReports: {},
  view: 'home',
  checklistSectionId: null,
  closeRoutineId: null,
  adminSectionId: null,
  taskSearch: '',
  showInactiveItems: false,
  historyLoaded: false,
  calendarLoaded: false,
  usersLoaded: false,
  editingItemId: null
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
    let message = 'Error de operacion.';
    try {
      const payload = await res.json();
      message = payload.detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return null;
  return res.json();
};

function toast(message) {
  const box = $('#toast');
  box.textContent = message;
  box.classList.add('show');
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => box.classList.remove('show'), 2800);
}

function pad2(value) {
  return String(value).padStart(2, '0');
}

function formatDateTimeLocal(date = new Date()) {
  return {
    date: `${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}/${date.getFullYear()}`,
    time: `${pad2(date.getHours())}:${pad2(date.getMinutes())}`,
    iso: date.toISOString()
  };
}

function monthKey(date = state.calendarDate) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;
}

function parseDateKey(dateKey) {
  const [year, month, day] = dateKey.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function formatDateKey(dateKey) {
  return new Intl.DateTimeFormat('es-PY', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).format(parseDateKey(dateKey));
}

function formatMonthLabel(date) {
  return new Intl.DateTimeFormat('es-PY', { month: 'long', year: 'numeric' }).format(date);
}

function routineById(routineId) {
  return state.routines.find((routine) => routine.id === routineId) || null;
}

function allTasks() {
  return state.routines.flatMap((routine) => routine.tasks.map((task) => ({ ...task, routine_title: routine.title })));
}

function storageKey(taskId, type = 'checked') {
  const userId = state.user?.id || 'guest';
  return `checklist-hogar:${userId}:${type}:${taskId}`;
}

function taskChecked(taskId) {
  return localStorage.getItem(storageKey(taskId)) === '1';
}

function taskNote(taskId) {
  return localStorage.getItem(storageKey(taskId, 'note')) || '';
}

function setTaskChecked(taskId, checked) {
  localStorage.setItem(storageKey(taskId), checked ? '1' : '0');
}

function setTaskNote(taskId, note) {
  localStorage.setItem(storageKey(taskId, 'note'), note || '');
}

function checkedTaskIdsForRoutine(routineId) {
  const tasks = getTasksForRoutine(routineId);
  return tasks.filter((task) => taskChecked(task.id)).map((task) => task.id);
}

function notesForRoutine(routineId) {
  const notes = {};
  getTasksForRoutine(routineId).forEach((task) => {
    const value = taskNote(task.id).trim();
    if (value) notes[task.id] = value;
  });
  return notes;
}

function getTasksForRoutine(routineId) {
  if (!routineId || routineId === 'all') return allTasks();
  return routineById(routineId)?.tasks || [];
}

function clearRoutineStorage(routineId) {
  getTasksForRoutine(routineId).forEach((task) => {
    localStorage.removeItem(storageKey(task.id));
    localStorage.removeItem(storageKey(task.id, 'note'));
  });
}

function sectionProgress(routineId) {
  const tasks = getTasksForRoutine(routineId);
  const total = tasks.length;
  const completed = tasks.filter((task) => taskChecked(task.id)).length;
  const percent = total ? Math.round((completed / total) * 1000) / 10 : 0;
  return { total, completed, pending: Math.max(total - completed, 0), percent };
}

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function showLogin() {
  $('#loginScreen').hidden = false;
  $('#appShell').hidden = true;
}

function showApp() {
  $('#loginScreen').hidden = true;
  $('#appShell').hidden = false;
}

function syncUserChrome() {
  $('#sidebarUserName').textContent = state.user?.name || 'Usuario';
  $('#sidebarUserMeta').textContent = state.user ? `${state.user.email} · ${state.user.role}` : '';
  const isAdmin = state.user?.role === 'admin';
  $$('.admin-only').forEach((el) => {
    el.hidden = !isAdmin;
  });
}

function renderNavState() {
  const meta = VIEW_META[state.view] || VIEW_META.home;
  $('#viewEyebrow').textContent = meta.eyebrow;
  $('#viewTitle').textContent = meta.title;
  $$('[data-view-target]').forEach((button) => {
    const target = button.dataset.viewTarget;
    button.classList.toggle('is-active', target === state.view);
  });
  $$('.view-panel').forEach((panel) => {
    panel.hidden = panel.id !== `view-${state.view}`;
  });
}

function closeMobileMenu() {
  $('#mobileMoreMenu').hidden = true;
}

async function setView(view) {
  state.view = view;
  renderNavState();
  closeMobileMenu();
  if (view === 'home') {
    if (!state.historyLoaded) await loadHistory();
    renderHome();
  }
  if (view === 'checklist') renderChecklistView();
  if (view === 'close') renderCloseView();
  if (view === 'history') {
    await loadHistory();
    renderHistory();
  }
  if (view === 'calendar') {
    await loadCalendar();
    renderCalendar();
  }
  if (view === 'admin') {
    await loadAdminView();
  }
}

async function loadChecklist() {
  const payload = await api('/api/checklist');
  state.routines = payload.routines || [];
  state.user = payload.user;
  state.checklistSectionId ||= state.routines[0]?.id || null;
  state.closeRoutineId ||= state.checklistSectionId;
  state.adminSectionId ||= state.checklistSectionId;
  syncUserChrome();
  fillRoutineSelect();
  fillAdminSectionSelect();
}

async function loadHistory() {
  const payload = await api('/api/runs?limit=30');
  state.history = payload.runs || [];
  state.historyLoaded = true;
}

async function loadCalendar() {
  const payload = await api(`/api/reports/calendar?month=${monthKey()}`);
  state.calendarReports = Object.fromEntries((payload.days || []).map((day) => [day.date, day]));
  state.calendarLoaded = true;
  if (!state.selectedCalendarDate) {
    const todayKey = new Date().toISOString().slice(0, 10);
    state.selectedCalendarDate = state.calendarReports[todayKey] ? todayKey : Object.keys(state.calendarReports)[0] || todayKey;
  }
}

async function loadUsers() {
  if (state.user?.role !== 'admin') return;
  const payload = await api('/api/users');
  state.users = payload.users || [];
  state.usersLoaded = true;
}

async function loadAdminItems() {
  if (state.user?.role !== 'admin' || !state.adminSectionId) return;
  const query = new URLSearchParams({ section_key: state.adminSectionId, include_inactive: String(state.showInactiveItems) });
  const payload = await api(`/api/admin/checklist/items?${query.toString()}`);
  state.adminItems = payload.items || [];
}

async function loadAdminView() {
  renderAdminShell();
  if (state.user?.role !== 'admin') return;
  await Promise.all([loadAdminItems(), loadUsers()]);
  renderAdminShell();
}

function renderHome() {
  const completedToday = state.history[0]?.percent ?? 0;
  const totalTasks = allTasks().length;
  const currentProgress = sectionProgress(state.checklistSectionId);
  $('#homeStats').innerHTML = [
    { label: 'Seccion activa', value: routineById(state.checklistSectionId)?.title || 'Sin datos' },
    { label: 'Progreso actual', value: `${currentProgress.completed}/${currentProgress.total}` },
    { label: 'Ultimo cierre', value: `${completedToday}%` },
    { label: 'Tareas activas', value: String(totalTasks) }
  ].map((item) => `
    <div class="stat-card">
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(item.value)}</strong>
    </div>
  `).join('');

  $('#homeRoutineButtons').innerHTML = state.routines.map((routine) => {
    const stats = sectionProgress(routine.id);
    return `
      <button class="quick-button" type="button" data-open-routine="${routine.id}">
        <span>${escapeHtml(routine.title)}</span>
        <small>${stats.completed}/${stats.total} · ${escapeHtml(routine.frequency)}</small>
      </button>
    `;
  }).join('');

  const preview = state.history.slice(0, 4);
  $('#homeHistoryPreview').innerHTML = preview.length ? preview.map((run) => `
    <article class="history-card">
      <div>
        <h4>${escapeHtml(run.routine_title)}</h4>
        <p>${escapeHtml(run.responsible)} · ${escapeHtml(run.user_name || '')}</p>
        <p>${escapeHtml(run.client_closed_at || run.server_closed_at || '')}</p>
      </div>
      <div class="badge-row">
        <span class="badge success">${run.completed_count}/${run.total_count}</span>
        <span class="badge">${run.percent}%</span>
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin cierres</strong><p>Cuando cierres una seccion apareceran aqui.</p></div>`;
}

function renderRoutineTabs(containerId, activeId, action) {
  const container = $(containerId);
  container.innerHTML = state.routines.map((routine) => `
    <button class="tab-button ${routine.id === activeId ? 'is-active' : ''}" type="button" data-${action}="${routine.id}">
      ${escapeHtml(routine.title)}
    </button>
  `).join('');
}

function renderChecklistView() {
  const routine = routineById(state.checklistSectionId) || state.routines[0];
  if (!routine) return;
  state.checklistSectionId = routine.id;
  renderRoutineTabs('#checklistTabs', routine.id, 'checklist-section');
  const stats = sectionProgress(routine.id);
  $('#checklistSummary').innerHTML = `
    <div class="summary-chip"><strong>${escapeHtml(routine.title)}</strong><span>${escapeHtml(routine.frequency)}</span></div>
    <div class="summary-chip"><strong>${routine.tasks.length} tareas</strong><span>${escapeHtml(routine.description)}</span></div>
    <div class="summary-chip"><strong>${stats.completed}/${stats.total} completadas</strong><span>${stats.pending} pendientes</span></div>
  `;
  $('#sectionProgressText').textContent = `${stats.completed} de ${stats.total} completadas`;
  $('#sectionProgressPercent').textContent = `${stats.percent}%`;
  $('#sectionProgressBar').style.width = `${stats.percent}%`;

  const search = state.taskSearch.trim().toLowerCase();
  const tasks = routine.tasks.filter((task) => {
    if (!search) return true;
    return [task.title, task.zone, routine.title].join(' ').toLowerCase().includes(search);
  });

  $('#checklistTaskList').innerHTML = tasks.length ? tasks.map((task) => {
    const checked = taskChecked(task.id);
    return `
      <article class="task-item ${checked ? 'is-done' : ''}">
        <label class="task-toggle">
          <input type="checkbox" data-task-toggle="${task.id}" ${checked ? 'checked' : ''}>
          <span class="checkmark" aria-hidden="true"></span>
        </label>
        <div class="task-copy">
          <strong>${escapeHtml(task.title)}</strong>
          <small>${escapeHtml(task.zone)}</small>
        </div>
        <textarea data-task-note="${task.id}" placeholder="Nota opcional">${escapeHtml(taskNote(task.id))}</textarea>
      </article>
    `;
  }).join('') : `<div class="empty-state"><strong>Sin coincidencias</strong><p>No hay tareas que coincidan con el filtro dentro de esta seccion.</p></div>`;
}

function fillRoutineSelect() {
  const current = state.closeRoutineId || state.checklistSectionId;
  $('#closeRoutine').innerHTML = [
    ...state.routines.map((routine) => `<option value="${routine.id}">${escapeHtml(routine.title)}</option>`),
    '<option value="all">Todas las secciones</option>'
  ].join('');
  $('#closeRoutine').value = current || state.routines[0]?.id || 'all';
}

function closePreviewData(routineId) {
  const tasks = getTasksForRoutine(routineId);
  const completedIds = checkedTaskIdsForRoutine(routineId);
  const completed = tasks.filter((task) => completedIds.includes(task.id));
  const pending = tasks.filter((task) => !completedIds.includes(task.id));
  const percent = tasks.length ? Math.round((completed.length / tasks.length) * 1000) / 10 : 0;
  const notes = tasks
    .map((task) => ({ title: task.title, note: taskNote(task.id) }))
    .filter((entry) => entry.note.trim());
  return { tasks, completed, pending, percent, notes };
}

function renderCloseView() {
  const now = formatDateTimeLocal();
  const responsible = $('#closeResponsible');
  const selectedValue = state.closeRoutineId || state.checklistSectionId || state.routines[0]?.id || 'all';
  fillRoutineSelect();
  $('#closeRoutine').value = selectedValue;
  $('#closeDate').value = now.date;
  $('#closeTime').value = now.time;
  if (!responsible.value.trim()) responsible.value = state.user?.name || '';
  renderClosePreview();
}

function renderClosePreview() {
  state.closeRoutineId = $('#closeRoutine').value;
  const info = closePreviewData(state.closeRoutineId);
  const label = state.closeRoutineId === 'all' ? 'Todas las secciones' : routineById(state.closeRoutineId)?.title || 'Seccion';
  $('#closePreview').innerHTML = `
    <strong>${escapeHtml(label)}</strong>
    <p>Total: <strong>${info.tasks.length}</strong> · Realizadas: <strong>${info.completed.length}</strong> · Pendientes: <strong>${info.pending.length}</strong> · Porcentaje: <strong>${info.percent}%</strong></p>
    ${info.notes.length ? `<ul>${info.notes.slice(0, 6).map((entry) => `<li><strong>${escapeHtml(entry.title)}:</strong> ${escapeHtml(entry.note)}</li>`).join('')}</ul>` : '<p>Sin notas guardadas para esta seccion.</p>'}
  `;
}

function renderHistory() {
  $('#historyList').innerHTML = state.history.length ? state.history.map((run) => `
    <article class="history-card">
      <div>
        <h4>${escapeHtml(run.routine_title)}</h4>
        <p>${escapeHtml(run.responsible)} · ${escapeHtml(run.user_name || '')}</p>
        <p>${escapeHtml(run.client_closed_at || run.server_closed_at || '')}</p>
        <p>${run.completed_count}/${run.total_count} completadas · ${run.pending_count} pendientes · ${run.percent}%</p>
      </div>
      <div class="item-actions">
        <a href="/api/runs/${run.id}/receipt" target="_blank" rel="noreferrer">Comprobante</a>
        <a href="/api/runs/${run.id}/export.csv">CSV</a>
        <a href="/api/runs/${run.id}/export.json">JSON</a>
        <button type="button" data-delete-run="${run.id}">Eliminar</button>
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin registros</strong><p>Todavia no hay cierres guardados.</p></div>`;
}

function renderCalendar() {
  $('#calendarMonthLabel').textContent = formatMonthLabel(state.calendarDate);
  const firstDay = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth(), 1);
  const firstWeekday = (firstDay.getDay() + 6) % 7;
  const startDate = new Date(firstDay);
  startDate.setDate(firstDay.getDate() - firstWeekday);
  const todayKey = new Date().toISOString().slice(0, 10);
  const days = [];
  for (let i = 0; i < 42; i += 1) {
    const current = new Date(startDate);
    current.setDate(startDate.getDate() + i);
    const key = current.toISOString().slice(0, 10);
    const monthMatch = current.getMonth() === state.calendarDate.getMonth();
    const reports = state.calendarReports[key];
    days.push(`
      <button type="button" class="calendar-day ${monthMatch ? '' : 'muted'} ${reports ? 'has-reports' : ''} ${state.selectedCalendarDate === key ? 'selected' : ''} ${todayKey === key ? 'today' : ''}" data-calendar-date="${key}">
        <span class="day-number">${current.getDate()}</span>
        ${reports ? `<span class="report-badge">${reports.count}</span>` : ''}
      </button>
    `);
  }
  $('#calendarGrid').innerHTML = days.join('');
  renderCalendarDetails();
}

function renderCalendarDetails() {
  const day = state.calendarReports[state.selectedCalendarDate];
  if (!day) {
    $('#calendarDetails').innerHTML = `<div class="empty-state"><strong>${escapeHtml(formatDateKey(state.selectedCalendarDate))}</strong><p>Sin cierres guardados en esta fecha.</p></div>`;
    return;
  }
  $('#calendarDetails').innerHTML = `
    <div class="panel-head">
      <div>
        <span class="eyebrow">Dia seleccionado</span>
        <h3>${escapeHtml(formatDateKey(day.date))}</h3>
      </div>
      <span class="badge">${day.count} cierre(s)</span>
    </div>
    <div class="stack-list">
      ${day.runs.map((run) => `
        <article class="history-card">
          <div>
            <h4>${escapeHtml(run.routine_title)}</h4>
            <p>${escapeHtml(run.responsible)} · ${run.completed_count}/${run.total_count} · ${run.percent}%</p>
          </div>
          <div class="item-actions">
            <a href="/api/runs/${run.id}/receipt" target="_blank" rel="noreferrer">Abrir</a>
          </div>
        </article>
      `).join('')}
    </div>
  `;
}

function fillAdminSectionSelect() {
  $('#adminSectionFilter').innerHTML = state.routines.map((routine) => `<option value="${routine.id}">${escapeHtml(routine.title)}</option>`).join('');
  if (state.adminSectionId) $('#adminSectionFilter').value = state.adminSectionId;
}

function resetItemForm() {
  state.editingItemId = null;
  $('#itemId').value = '';
  $('#itemTitle').value = '';
  $('#itemZone').value = '';
  $('#itemOrder').value = String((state.adminItems.at(-1)?.sort_order || 0) + 1);
  $('#itemActive').checked = true;
  $('#saveItemBtn').textContent = 'Guardar item';
}

function renderAdminShell() {
  const denied = $('#adminDenied');
  const content = $('#adminContent');
  const isAdmin = state.user?.role === 'admin';
  denied.hidden = isAdmin;
  content.hidden = !isAdmin;
  if (!isAdmin) return;
  fillAdminSectionSelect();
  $('#showInactiveItems').checked = state.showInactiveItems;
  $('#adminItemsList').innerHTML = state.adminItems.length ? state.adminItems.map((item) => `
    <article class="admin-item">
      <div>
        <h4>${escapeHtml(item.title)}</h4>
        <p>${escapeHtml(item.zone)} · Orden ${item.sort_order} · ${escapeHtml(item.section_title || '')}</p>
        <p>${item.active ? 'Activo' : 'Inactivo'} · ID ${escapeHtml(item.id)}</p>
      </div>
      <div class="item-actions">
        <button type="button" data-edit-item="${item.id}">Editar</button>
        <button type="button" data-toggle-item="${item.id}" data-active="${item.active}">${item.active ? 'Desactivar' : 'Activar'}</button>
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin items</strong><p>No hay items cargados para esta seccion.</p></div>`;

  $('#usersList').innerHTML = state.users.length ? state.users.map((user) => `
    <article class="user-item">
      <div>
        <h4>${escapeHtml(user.name)}</h4>
        <p>${escapeHtml(user.email)} · ${escapeHtml(user.role)}</p>
      </div>
      <div class="badge-row"><span class="badge ${user.is_active ? 'success' : 'warning'}">${user.is_active ? 'Activo' : 'Inactivo'}</span></div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin usuarios</strong><p>No hay usuarios para mostrar.</p></div>`;

  if (!state.editingItemId) resetItemForm();
}

function editItem(itemId) {
  const item = state.adminItems.find((entry) => entry.id === itemId);
  if (!item) return;
  state.editingItemId = itemId;
  $('#itemId').value = item.id;
  $('#itemTitle').value = item.title;
  $('#itemZone').value = item.zone;
  $('#itemOrder').value = String(item.sort_order);
  $('#itemActive').checked = Boolean(item.active);
  $('#saveItemBtn').textContent = 'Actualizar item';
}

async function submitItemForm(event) {
  event.preventDefault();
  const payload = {
    section_key: $('#adminSectionFilter').value,
    title: $('#itemTitle').value.trim(),
    zone: $('#itemZone').value.trim(),
    sort_order: Number($('#itemOrder').value || 0),
    active: $('#itemActive').checked
  };
  if (!payload.title || !payload.zone) {
    toast('Completa titulo y zona.');
    return;
  }
  if (state.editingItemId) {
    await api(`/api/admin/checklist/items/${state.editingItemId}`, { method: 'PUT', body: JSON.stringify(payload) });
    toast('Item actualizado.');
  } else {
    await api('/api/admin/checklist/items', { method: 'POST', body: JSON.stringify(payload) });
    toast('Item creado.');
  }
  await loadChecklist();
  await loadAdminItems();
  renderChecklistView();
  resetItemForm();
  renderAdminShell();
}

async function toggleItem(itemId, active) {
  if (active) {
    await api(`/api/admin/checklist/items/${itemId}`, { method: 'DELETE' });
    toast('Item desactivado.');
  } else {
    await api(`/api/admin/checklist/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify({ active: true, section_key: $('#adminSectionFilter').value })
    });
    toast('Item reactivado.');
  }
  await loadChecklist();
  await loadAdminItems();
  renderChecklistView();
  renderAdminShell();
}

async function submitUserForm(event) {
  event.preventDefault();
  await api('/api/users', {
    method: 'POST',
    body: JSON.stringify({
      name: $('#newUserName').value.trim(),
      email: $('#newUserEmail').value.trim(),
      password: $('#newUserPassword').value,
      role: $('#newUserRole').value
    })
  });
  event.target.reset();
  toast('Usuario creado.');
  await loadUsers();
  renderAdminShell();
}

async function submitCloseForm(event) {
  event.preventDefault();
  const routineId = $('#closeRoutine').value;
  const payload = {
    routine_id: routineId,
    responsible: $('#closeResponsible').value.trim(),
    observations: $('#closeObservations').value.trim(),
    completed_task_ids: checkedTaskIdsForRoutine(routineId),
    notes_by_task: notesForRoutine(routineId),
    include_pending: $('#includePending').checked,
    client_closed_at: `${$('#closeDate').value} ${$('#closeTime').value}`
  };
  if (!payload.completed_task_ids.length) {
    toast('Marca al menos una tarea en la seccion seleccionada.');
    return;
  }
  const result = await api('/api/runs', { method: 'POST', body: JSON.stringify(payload) });
  if (routineId === 'all') {
    clearRoutineStorage('all');
  } else {
    clearRoutineStorage(routineId);
  }
  await loadHistory();
  await loadCalendar();
  renderChecklistView();
  renderCloseView();
  toast(`Cierre guardado: ${result.percent}%`);
  window.open(`/api/runs/${result.run_id}/receipt`, '_blank', 'noopener');
  await setView('history');
}

async function login(event) {
  event.preventDefault();
  $('#loginError').textContent = '';
  try {
    const payload = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: $('#loginEmail').value.trim(), password: $('#loginPassword').value })
    });
    state.user = payload.user;
    await bootApp();
    toast('Sesion iniciada.');
  } catch (error) {
    $('#loginError').textContent = error.message;
  }
}

async function logout() {
  try {
    await api('/api/auth/logout', { method: 'POST' });
  } catch (_) {}
  state.user = null;
  state.history = [];
  state.users = [];
  state.adminItems = [];
  state.historyLoaded = false;
  state.usersLoaded = false;
  showLogin();
}

async function deleteRun(runId) {
  if (!confirm('Se eliminara este cierre del historial.')) return;
  await api(`/api/runs/${runId}`, { method: 'DELETE' });
  await loadHistory();
  if (state.view === 'history') renderHistory();
  if (state.view === 'home') renderHome();
  toast('Cierre eliminado.');
}

async function bootApp() {
  await loadChecklist();
  await loadHistory();
  showApp();
  syncUserChrome();
  renderNavState();
  renderHome();
  renderChecklistView();
  renderCloseView();
  await setView(state.view || 'home');
}

async function init() {
  bindStaticEvents();
  try {
    const payload = await api('/api/users/me');
    state.user = payload.user;
    await bootApp();
  } catch (_) {
    showLogin();
  }
}

function bindStaticEvents() {
  $('#loginForm').addEventListener('submit', login);
  $('#logoutBtn').addEventListener('click', logout);
  $('#mobileLogoutBtn').addEventListener('click', logout);
  $('#quickChecklistBtn').addEventListener('click', () => setView('checklist'));
  $('#quickCloseBtn').addEventListener('click', () => {
    state.closeRoutineId = state.checklistSectionId;
    setView('close');
  });
  $('#homeChecklistBtn').addEventListener('click', () => setView('checklist'));
  $('#homeCloseBtn').addEventListener('click', () => {
    state.closeRoutineId = state.checklistSectionId;
    setView('close');
  });
  $('#taskSearch').addEventListener('input', (event) => {
    state.taskSearch = event.target.value;
    renderChecklistView();
  });
  $('#saveProgressBtn').addEventListener('click', () => toast('Avance guardado localmente.'));
  $('#openCloseFromChecklistBtn').addEventListener('click', () => {
    state.closeRoutineId = state.checklistSectionId;
    setView('close');
  });
  $('#clearSectionBtn').addEventListener('click', () => {
    clearRoutineStorage(state.checklistSectionId);
    renderChecklistView();
    renderCloseView();
    toast('Seccion limpiada.');
  });
  $('#closeRoutine').addEventListener('change', renderClosePreview);
  $('#includePending').addEventListener('change', renderClosePreview);
  $('#resetCloseViewBtn').addEventListener('click', renderCloseView);
  $('#closeRunForm').addEventListener('submit', submitCloseForm);
  $('#reloadHistoryBtn').addEventListener('click', async () => {
    await loadHistory();
    renderHistory();
    toast('Historial actualizado.');
  });
  $('#prevMonthBtn').addEventListener('click', async () => {
    state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() - 1, 1);
    state.selectedCalendarDate = null;
    await loadCalendar();
    renderCalendar();
  });
  $('#nextMonthBtn').addEventListener('click', async () => {
    state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() + 1, 1);
    state.selectedCalendarDate = null;
    await loadCalendar();
    renderCalendar();
  });
  $('#adminSectionFilter').addEventListener('change', async (event) => {
    state.adminSectionId = event.target.value;
    resetItemForm();
    await loadAdminItems();
    renderAdminShell();
  });
  $('#showInactiveItems').addEventListener('change', async (event) => {
    state.showInactiveItems = event.target.checked;
    await loadAdminItems();
    renderAdminShell();
  });
  $('#resetItemFormBtn').addEventListener('click', resetItemForm);
  $('#itemForm').addEventListener('submit', submitItemForm);
  $('#userForm').addEventListener('submit', submitUserForm);
  $('#mobileMoreBtn').addEventListener('click', () => {
    $('#mobileMoreMenu').hidden = !$('#mobileMoreMenu').hidden;
  });

  document.addEventListener('click', async (event) => {
    const viewButton = event.target.closest('[data-view-target]');
    if (viewButton) {
      const targetView = viewButton.dataset.viewTarget;
      if (targetView === 'admin' && state.user?.role !== 'admin') return;
      await setView(targetView);
      return;
    }

    const routineButton = event.target.closest('[data-open-routine]');
    if (routineButton) {
      state.checklistSectionId = routineButton.dataset.openRoutine;
      renderChecklistView();
      await setView('checklist');
      return;
    }

    const sectionButton = event.target.closest('[data-checklist-section]');
    if (sectionButton) {
      state.checklistSectionId = sectionButton.dataset.checklistSection;
      state.taskSearch = '';
      $('#taskSearch').value = '';
      renderChecklistView();
      return;
    }

    const toggle = event.target.closest('[data-delete-run]');
    if (toggle) {
      await deleteRun(toggle.dataset.deleteRun);
      return;
    }

    const calendarDate = event.target.closest('[data-calendar-date]');
    if (calendarDate) {
      state.selectedCalendarDate = calendarDate.dataset.calendarDate;
      renderCalendar();
      return;
    }

    const editButton = event.target.closest('[data-edit-item]');
    if (editButton) {
      editItem(editButton.dataset.editItem);
      return;
    }

    const toggleItemButton = event.target.closest('[data-toggle-item]');
    if (toggleItemButton) {
      await toggleItem(toggleItemButton.dataset.toggleItem, toggleItemButton.dataset.active === '1');
      return;
    }

    if (!event.target.closest('#mobileMoreMenu') && !event.target.closest('#mobileMoreBtn')) {
      closeMobileMenu();
    }
  });

  document.addEventListener('change', (event) => {
    const checkbox = event.target.closest('[data-task-toggle]');
    if (checkbox) {
      setTaskChecked(checkbox.dataset.taskToggle, checkbox.checked);
      renderChecklistView();
      renderClosePreview();
    }
  });

  document.addEventListener('input', (event) => {
    const note = event.target.closest('[data-task-note]');
    if (note) {
      setTaskNote(note.dataset.taskNote, note.value);
      renderClosePreview();
    }
  });
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/static/service-worker.js').catch(() => {}));
}

init();
