import { $, $$, api, toast, escapeHtml } from '/static/api.js';
import { formatDateKey, formatDateTimeLocal, formatMonthLabel, isPastDateKey, localDateKey, monthKey, parseDateKey } from '/static/date.js';
import { ROLE_LABELS, VIEW_META, state } from '/static/state.js';

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

function getTasksForRoutine(routineId) {
  if (!routineId || routineId === 'all') return allTasks();
  return routineById(routineId)?.tasks || [];
}

function checkedTaskIdsForRoutine(routineId) {
  return getTasksForRoutine(routineId).filter((task) => taskChecked(task.id)).map((task) => task.id);
}

function notesForRoutine(routineId) {
  const notes = {};
  getTasksForRoutine(routineId).forEach((task) => {
    const value = taskNote(task.id).trim();
    if (value) notes[task.id] = value;
  });
  return notes;
}

function clearRoutineStorage(routineId) {
  getTasksForRoutine(routineId).forEach((task) => {
    localStorage.removeItem(storageKey(task.id));
    localStorage.removeItem(storageKey(task.id, 'note'));
  });
}

function routineHasLocalDraft(routineId) {
  return getTasksForRoutine(routineId).some((task) => taskChecked(task.id) || taskNote(task.id).trim());
}

function sectionProgress(routineId) {
  const tasks = getTasksForRoutine(routineId);
  const total = tasks.length;
  const completed = tasks.filter((task) => taskChecked(task.id)).length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  return { total, completed, pending: Math.max(total - completed, 0), percent };
}

function setStatus(message, tone = 'info') {
  state.statusMessage = message;
  state.statusTone = tone;
  const box = $('#globalStatus');
  if (!box) return;
  box.textContent = message;
  box.dataset.tone = tone;
  box.hidden = !message;
}

function showLogin() {
  $('#loginScreen').hidden = false;
  $('#appShell').hidden = true;
}

function showApp() {
  $('#loginScreen').hidden = true;
  $('#appShell').hidden = false;
}

function canWrite() {
  return ['admin', 'usuario'].includes(state.user?.role);
}

function isAdmin() {
  return state.user?.role === 'admin';
}

function syncUserChrome() {
  $('#sidebarUserName').textContent = state.user?.username || 'Usuario';
  $('#sidebarUserMeta').textContent = state.user ? `${ROLE_LABELS[state.user.role] || state.user.role}` : '';
  const admin = isAdmin();
  const writer = canWrite();
  $$('.admin-only').forEach((el) => { el.hidden = !admin; });
  $$('.writer-only').forEach((el) => { el.hidden = !writer; });
  $$('.readonly-only').forEach((el) => { el.hidden = state.user?.role !== 'solo_lectura'; });
}

function renderNavState() {
  const meta = VIEW_META[state.view] || VIEW_META.home;
  $('#viewEyebrow').textContent = meta.eyebrow;
  $('#viewTitle').textContent = meta.title;
  $$('[data-view-target]').forEach((button) => {
    const active = button.dataset.viewTarget === state.view;
    button.classList.toggle('is-active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  $$('.view-panel').forEach((panel) => { panel.hidden = panel.id !== `view-${state.view}`; });
}

function closeMobileMenu() {
  $('#mobileMoreMenu').hidden = true;
  $('#mobileMoreBtn').setAttribute('aria-expanded', 'false');
}

async function setView(view) {
  state.view = view;
  renderNavState();
  closeMobileMenu();
  if (view === 'home') renderHome();
  if (view === 'checklist') renderChecklistView();
  if (view === 'close') renderCloseView();
  if (view === 'history') {
    if (!state.history.length) await loadHistory(true);
    renderHistory();
  }
  if (view === 'calendar') {
    await loadCalendar();
    renderCalendar();
  }
  if (view === 'admin') await loadAdminView();
}

async function loadChecklist() {
  const payload = await api('/api/checklist');
  state.routines = payload.routines || [];
  state.user = payload.user;
  state.categories = payload.categories || [];
  state.roles = payload.roles || [];
  state.checklistSectionId ||= state.routines[0]?.id || null;
  state.closeRoutineId ||= state.checklistSectionId || 'all';
  state.adminSectionId ||= state.checklistSectionId;
  syncUserChrome();
  fillRoutineSelect();
  fillAdminSectionSelect();
}

async function loadHistory(reset = false) {
  const offset = reset ? 0 : state.historyOffset;
  const payload = await api(`/api/runs?limit=20&offset=${offset}`);
  if (reset) state.history = payload.runs || [];
  else state.history.push(...(payload.runs || []));
  state.historyOffset = payload.next_offset || 0;
  state.historyHasMore = Boolean(payload.has_more);
}

async function loadCalendar() {
  const payload = await api(`/api/reports/calendar?month=${monthKey(state.calendarDate)}`);
  state.calendarReports = Object.fromEntries((payload.days || []).map((day) => [day.date, day]));
  if (!state.selectedCalendarDate) {
    const todayKey = localDateKey();
    state.selectedCalendarDate = state.calendarReports[todayKey] ? todayKey : Object.keys(state.calendarReports)[0] || todayKey;
  }
}

async function loadUsers() {
  if (!isAdmin()) return;
  const payload = await api('/api/users');
  state.users = payload.users || [];
}

async function loadAdminItems() {
  if (!isAdmin() || !state.adminSectionId) return;
  const query = new URLSearchParams({ section_key: state.adminSectionId, include_inactive: String(state.showInactiveItems) });
  const payload = await api(`/api/admin/checklist/items?${query.toString()}`);
  state.adminItems = payload.items || [];
  state.categories = payload.categories || state.categories;
}

async function loadBackups() {
  if (!isAdmin()) return;
  const payload = await api('/api/admin/backups');
  state.backups = payload.backups || [];
}

async function loadActivity() {
  if (!isAdmin()) return;
  const payload = await api('/api/admin/activity?limit=25');
  state.activity = payload.activity || [];
}

async function loadAdminView() {
  renderAdminShell();
  if (!isAdmin()) return;
  await Promise.all([loadAdminItems(), loadUsers(), loadBackups(), loadActivity()]);
  renderAdminShell();
}

function fillRoutineSelect() {
  $('#closeRoutine').innerHTML = [
    ...state.routines.map((routine) => `<option value="${routine.id}">${escapeHtml(routine.title)}</option>`),
    '<option value="all">Todas las secciones</option>'
  ].join('');
  $('#closeRoutine').value = state.closeRoutineId || state.routines[0]?.id || 'all';
}

function fillAdminSectionSelect() {
  $('#adminSectionFilter').innerHTML = state.routines.map((routine) => `<option value="${routine.id}">${escapeHtml(routine.title)}</option>`).join('');
  if (state.adminSectionId) $('#adminSectionFilter').value = state.adminSectionId;
  $('#itemCategory').innerHTML = state.categories.map((category) => `<option value="${category}">${escapeHtml(category)}</option>`).join('');
}

function renderHome() {
  const currentProgress = sectionProgress(state.checklistSectionId);
  $('#homeStats').innerHTML = [
    { label: 'Usuario activo', value: state.user?.username || 'Sin sesion' },
    { label: 'Rol', value: ROLE_LABELS[state.user?.role] || state.user?.role || '-' },
    { label: 'Progreso actual', value: `${currentProgress.completed}/${currentProgress.total}` },
    { label: 'Ultimo cierre', value: state.history[0]?.local_closed_at || 'Sin registros' }
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
        <p>${escapeHtml(run.responsible)} · ${escapeHtml(run.user_username || '')}</p>
        <p>${escapeHtml(run.local_closed_at || '')}</p>
      </div>
      <div class="badge-row">
        <span class="badge ${run.percent === 100 ? 'success' : 'warning'}">${run.percent}%</span>
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin cierres</strong><p>Cuando generes un cierre aparecerá aquí.</p></div>`;
}

function renderRoutineTabs(containerId, activeId, action) {
  $(containerId).innerHTML = state.routines.map((routine) => `
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
    <div class="summary-chip"><strong>${routine.tasks.length} items</strong><span>${escapeHtml(routine.description)}</span></div>
    <div class="summary-chip"><strong>${stats.completed}/${stats.total} completados</strong><span>${stats.pending} pendientes</span></div>
  `;
  $('#sectionProgressText').textContent = `${stats.completed} de ${stats.total} completados`;
  $('#sectionProgressPercent').textContent = `${stats.percent}%`;
  $('#sectionProgressBar').style.width = `${stats.percent}%`;

  if (stats.total === 0) setStatus('Checklist incompleto', 'warning');
  else if (stats.percent === 100) setStatus('Checklist listo para generar cierre', 'success');
  else if (routineHasLocalDraft(routine.id)) setStatus('Avance guardado en este dispositivo', 'info');
  else setStatus('Checklist incompleto', 'warning');

  const search = state.taskSearch.trim().toLowerCase();
  const readonly = !canWrite();
  const tasks = routine.tasks.filter((task) => {
    if (!search) return true;
    return [task.title, task.zone, task.category, routine.title].join(' ').toLowerCase().includes(search);
  });

  $('#checklistTaskList').innerHTML = tasks.length ? tasks.map((task) => {
    const checked = taskChecked(task.id);
    return `
      <article class="task-item ${checked ? 'is-done' : ''}">
        <label class="task-toggle">
          <input type="checkbox" data-task-toggle="${task.id}" ${checked ? 'checked' : ''} ${readonly ? 'disabled' : ''} aria-label="Marcar ${escapeHtml(task.title)}">
          <span class="checkmark" aria-hidden="true"></span>
        </label>
        <div class="task-copy">
          <strong>${escapeHtml(task.title)}</strong>
          <small>${escapeHtml(task.zone)} · ${escapeHtml(task.category)} · ${task.is_required ? 'Obligatorio' : 'Opcional'}</small>
        </div>
        <textarea data-task-note="${task.id}" ${readonly ? 'disabled' : ''} placeholder="Nota opcional">${escapeHtml(taskNote(task.id))}</textarea>
      </article>
    `;
  }).join('') : `<div class="empty-state"><strong>Sin coincidencias</strong><p>No hay ítems que coincidan con el filtro actual.</p></div>`;
}

function closePreviewData(routineId) {
  const tasks = getTasksForRoutine(routineId);
  const completedIds = checkedTaskIdsForRoutine(routineId);
  const completed = tasks.filter((task) => completedIds.includes(task.id));
  const pending = tasks.filter((task) => !completedIds.includes(task.id));
  const percent = tasks.length ? Math.round((completed.length / tasks.length) * 100) : 0;
  return { tasks, completed, pending, percent };
}

function renderCloseView() {
  const now = formatDateTimeLocal();
  fillRoutineSelect();
  $('#closeRoutine').value = state.closeRoutineId || state.checklistSectionId || state.routines[0]?.id || 'all';
  $('#closeDate').value = now.dateKey;
  $('#closeTime').value = now.timeKey;
  if (!$('#closeResponsible').value.trim()) $('#closeResponsible').value = state.user?.username || '';
  renderClosePreview();
}

function renderClosePreview() {
  state.closeRoutineId = $('#closeRoutine').value;
  const info = closePreviewData(state.closeRoutineId);
  const label = state.closeRoutineId === 'all' ? 'Todas las secciones' : routineById(state.closeRoutineId)?.title || 'Seccion';
  $('#closePreview').innerHTML = `
    <strong>${escapeHtml(label)}</strong>
    <p>Total: <strong>${info.tasks.length}</strong> · Realizadas: <strong>${info.completed.length}</strong> · Pendientes: <strong>${info.pending.length}</strong> · Cumplimiento: <strong>${info.percent}%</strong></p>
  `;
}

function renderLastRunResult() {
  const panel = $('#closeResult');
  if (!state.lastRun) {
    panel.hidden = true;
    panel.innerHTML = '';
    return;
  }
  panel.hidden = false;
  panel.innerHTML = `
    <strong>Cierre generado</strong>
    <p>${escapeHtml(state.lastRun.local_closed_at)} · ${state.lastRun.percent}% completado</p>
    <div class="action-row compact">
      <a class="btn ghost-blue" href="/api/runs/${state.lastRun.run_id}/receipt" target="_blank" rel="noreferrer">Ver comprobante</a>
      <a class="btn" href="/api/runs/${state.lastRun.run_id}/receipt" target="_blank" rel="noreferrer">Descargar / Imprimir</a>
    </div>
  `;
}

function renderHistory() {
  $('#historyList').innerHTML = state.history.length ? state.history.map((run) => `
    <article class="history-card">
      <div>
        <h4>${escapeHtml(run.routine_title)}</h4>
        <p>${escapeHtml(run.responsible)} · ${escapeHtml(run.user_username || '')}</p>
        <p>${escapeHtml(run.local_closed_at || '')}</p>
        <p>${run.completed_count}/${run.total_count} completadas · ${run.pending_count} pendientes · ${run.percent}%</p>
      </div>
      <div class="item-actions">
        <a href="/api/runs/${run.id}/receipt" target="_blank" rel="noreferrer">Ver comprobante</a>
        <a href="/api/runs/${run.id}/export.csv">CSV</a>
        <a href="/api/runs/${run.id}/export.json">JSON</a>
        ${isAdmin() ? `<button type="button" data-delete-run="${run.id}">Desactivar</button>` : ''}
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin registros</strong><p>Todavía no hay cierres guardados.</p></div>`;
  $('#loadMoreHistoryBtn').hidden = !state.historyHasMore;
}

function calendarDayClass(day, key) {
  if (!day) return 'empty';
  if (day.status === 'complete') return 'complete';
  if (day.status === 'overdue') return 'overdue';
  if (day.status === 'incomplete' && isPastDateKey(key)) return 'overdue';
  return 'incomplete';
}

function renderCalendar() {
  $('#calendarMonthLabel').textContent = formatMonthLabel(state.calendarDate);
  const firstDay = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth(), 1);
  const firstWeekday = (firstDay.getDay() + 6) % 7;
  const startDate = new Date(firstDay);
  startDate.setDate(firstDay.getDate() - firstWeekday);
  const todayKey = localDateKey();
  const days = [];
  for (let i = 0; i < 42; i += 1) {
    const current = new Date(startDate);
    current.setDate(startDate.getDate() + i);
    const key = localDateKey(current);
    const monthMatch = current.getMonth() === state.calendarDate.getMonth();
    const reports = state.calendarReports[key];
    days.push(`
      <button type="button" class="calendar-day ${monthMatch ? '' : 'muted'} ${calendarDayClass(reports, key)} ${state.selectedCalendarDate === key ? 'selected' : ''} ${todayKey === key ? 'today' : ''}" data-calendar-date="${key}">
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
    $('#calendarDetails').innerHTML = `<div class="empty-state"><strong>${escapeHtml(formatDateKey(state.selectedCalendarDate))}</strong><p>Sin actividad en esta fecha.</p></div>`;
    return;
  }
  $('#calendarDetails').innerHTML = `
    <div class="panel-head">
      <div>
        <span class="eyebrow">Dia seleccionado</span>
        <h3>${escapeHtml(formatDateKey(day.date))}</h3>
      </div>
      <span class="badge ${day.status === 'complete' ? 'success' : day.status === 'overdue' ? 'danger' : 'warning'}">${day.status}</span>
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

function resetItemForm() {
  state.editingItemId = null;
  $('#itemId').value = '';
  $('#itemTitle').value = '';
  $('#itemZone').value = '';
  $('#itemOrder').value = String((state.adminItems.at(-1)?.sort_order || 0) + 1);
  $('#itemRequired').checked = true;
  $('#itemActive').checked = true;
  $('#itemCategory').value = state.categories[0] || 'Seguridad';
  $('#saveItemBtn').textContent = 'Guardar item';
}

function renderAdminShell() {
  const denied = $('#adminDenied');
  const content = $('#adminContent');
  denied.hidden = isAdmin();
  content.hidden = !isAdmin();
  if (!isAdmin()) return;
  fillAdminSectionSelect();
  $('#showInactiveItems').checked = state.showInactiveItems;
  $('#adminItemsList').innerHTML = state.adminItems.length ? state.adminItems.map((item) => `
    <article class="admin-item">
      <div>
        <h4>${escapeHtml(item.title)}</h4>
        <p>${escapeHtml(item.zone)} · ${escapeHtml(item.category)} · ${item.is_required ? 'Obligatorio' : 'Opcional'}</p>
        <p>Orden ${item.sort_order} · ${item.active ? 'Activo' : 'Inactivo'}</p>
      </div>
      <div class="item-actions">
        <button type="button" data-move-item="${item.id}" data-direction="up">Subir</button>
        <button type="button" data-move-item="${item.id}" data-direction="down">Bajar</button>
        <button type="button" data-edit-item="${item.id}">Editar</button>
        <button type="button" data-toggle-item="${item.id}" data-active="${item.active ? '1' : '0'}">${item.active ? 'Desactivar' : 'Activar'}</button>
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin items</strong><p>No hay items cargados para esta sección.</p></div>`;

  $('#usersList').innerHTML = state.users.length ? state.users.map((user) => `
    <article class="user-item">
      <div>
        <h4>${escapeHtml(user.username)}</h4>
        <p>Rol actual: ${escapeHtml(ROLE_LABELS[user.role] || user.role)}</p>
        <p>Último login: ${escapeHtml(user.last_login || 'Nunca')}</p>
      </div>
      <form class="user-actions" data-user-form="${user.id}">
        <select data-user-role="${user.id}" aria-label="Rol de ${escapeHtml(user.username)}">
          ${state.roles.map((role) => `<option value="${role}" ${role === user.role ? 'selected' : ''}>${escapeHtml(ROLE_LABELS[role] || role)}</option>`).join('')}
        </select>
        <label class="inline-check"><input type="checkbox" data-user-active="${user.id}" ${user.is_active ? 'checked' : ''}> Activo</label>
        <input type="password" data-user-password="${user.id}" placeholder="Nueva contraseña">
        <button type="submit">Guardar</button>
      </form>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin usuarios</strong><p>No hay usuarios para mostrar.</p></div>`;

  $('#backupsList').innerHTML = state.backups.length ? state.backups.map((backup) => `
    <article class="history-card">
      <div>
        <h4>${escapeHtml(backup.filename)}</h4>
        <p>${escapeHtml(backup.modified_at)} · ${backup.size} bytes</p>
      </div>
      <div class="item-actions">
        <a href="/api/admin/backups/${encodeURIComponent(backup.filename)}">Descargar</a>
        <button type="button" data-restore-backup="${backup.filename}">Restaurar</button>
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin backups</strong><p>Todavía no hay backups guardados.</p></div>`;

  $('#activityList').innerHTML = state.activity.length ? state.activity.map((entry) => `
    <article class="history-card compact-card">
      <div>
        <h4>${escapeHtml(entry.action)}</h4>
        <p>${escapeHtml(entry.username || 'sistema')} · ${escapeHtml(entry.created_at || '')}</p>
        <p>${escapeHtml(entry.details || '')}</p>
      </div>
    </article>
  `).join('') : `<div class="empty-state"><strong>Sin actividad</strong><p>No hay eventos registrados todavía.</p></div>`;

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
  $('#itemCategory').value = item.category;
  $('#itemRequired').checked = Boolean(item.is_required);
  $('#itemActive').checked = Boolean(item.active);
  $('#saveItemBtn').textContent = 'Actualizar item';
}

async function submitItemForm(event) {
  event.preventDefault();
  const payload = {
    section_key: $('#adminSectionFilter').value,
    title: $('#itemTitle').value.trim(),
    zone: $('#itemZone').value.trim(),
    category: $('#itemCategory').value,
    sort_order: Number($('#itemOrder').value || 0),
    is_required: $('#itemRequired').checked,
    active: $('#itemActive').checked
  };
  if (!payload.title || !payload.zone) {
    toast('Completa título y zona.', 'warning');
    return;
  }
  if (state.editingItemId) {
    await api(`/api/admin/checklist/items/${state.editingItemId}`, { method: 'PUT', body: JSON.stringify(payload) });
    toast('Item actualizado.', 'success');
  } else {
    await api('/api/admin/checklist/items', { method: 'POST', body: JSON.stringify(payload) });
    toast('Item creado.', 'success');
  }
  await loadChecklist();
  await loadAdminItems();
  renderChecklistView();
  resetItemForm();
  renderAdminShell();
}

async function moveItem(itemId, direction) {
  await api(`/api/admin/checklist/items/${itemId}/move`, { method: 'POST', body: JSON.stringify({ direction }) });
  await loadChecklist();
  await loadAdminItems();
  renderChecklistView();
  renderAdminShell();
}

async function toggleItem(itemId, active) {
  if (active) {
    await api(`/api/admin/checklist/items/${itemId}`, { method: 'DELETE' });
    toast('Item desactivado.', 'warning');
  } else {
    await api(`/api/admin/checklist/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify({ active: true, section_key: $('#adminSectionFilter').value })
    });
    toast('Item activado.', 'success');
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
      username: $('#newUsername').value.trim(),
      password: $('#newUserPassword').value,
      role: $('#newUserRole').value
    })
  });
  event.target.reset();
  toast('Usuario creado.', 'success');
  await loadUsers();
  await loadActivity();
  renderAdminShell();
}

async function saveUser(event) {
  event.preventDefault();
  const form = event.target.closest("[data-user-form]");
  const userId = form.dataset.userForm;
  const role = form.querySelector(`[data-user-role="${userId}"]`).value;
  const isActive = form.querySelector(`[data-user-active="${userId}"]`).checked;
  const password = form.querySelector(`[data-user-password="${userId}"]`).value;
  const payload = { role, is_active: isActive };
  if (password.trim()) payload.password = password;
  await api(`/api/users/${userId}`, { method: 'PUT', body: JSON.stringify(payload) });
  toast('Usuario actualizado.', 'success');
  await loadUsers();
  await loadActivity();
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
    local_date: $('#closeDate').value,
    local_time: $('#closeTime').value
  };
  if (!payload.completed_task_ids.length) {
    setStatus('Error al guardar: marca al menos una tarea.', 'danger');
    toast('Marca al menos una tarea en la sección seleccionada.', 'warning');
    return;
  }
  try {
    const result = await api('/api/runs', { method: 'POST', body: JSON.stringify(payload) });
    clearRoutineStorage(routineId);
    state.lastRun = result;
    await loadHistory(true);
    await loadCalendar();
    renderChecklistView();
    renderCloseView();
    renderLastRunResult();
    setStatus('Cierre generado', 'success');
    toast(`Cierre guardado: ${result.percent}%`, 'success');
  } catch (error) {
    setStatus('Error al guardar', 'danger');
    throw error;
  }
}

async function login(event) {
  event.preventDefault();
  $('#loginError').textContent = '';
  try {
    const payload = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username: $('#loginUsername').value.trim(), password: $('#loginPassword').value })
    });
    state.user = payload.user;
    await bootApp();
    toast('Sesión iniciada.', 'success');
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
  state.backups = [];
  state.activity = [];
  state.lastRun = null;
  showLogin();
}

async function deleteRun(runId) {
  if (!confirm('El cierre quedará desactivado del historial visible.')) return;
  await api(`/api/runs/${runId}`, { method: 'DELETE', body: JSON.stringify({ reason: 'Desactivado desde panel admin' }) });
  await loadHistory(true);
  if (state.view === 'history') renderHistory();
  if (state.view === 'home') renderHome();
  await loadActivity();
  toast('Cierre desactivado.', 'warning');
}

async function createBackup() {
  const result = await api('/api/admin/backups/create', { method: 'POST' });
  await loadBackups();
  await loadActivity();
  renderAdminShell();
  toast(`Backup creado: ${result.filename}`, 'success');
}

async function restoreBackup(filename) {
  if (!confirm(`Se restaurará ${filename}. Esto cerrará las sesiones actuales.`)) return;
  await api('/api/admin/backups/restore', { method: 'POST', body: JSON.stringify({ filename }) });
  toast('Backup restaurado. Vuelve a iniciar sesión.', 'warning');
  await logout();
}

async function bootApp() {
  await loadChecklist();
  await loadHistory(true);
  showApp();
  syncUserChrome();
  renderNavState();
  renderHome();
  renderChecklistView();
  renderCloseView();
  renderLastRunResult();
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
  $('#saveProgressBtn').addEventListener('click', () => {
    setStatus('Avance guardado en este dispositivo', 'info');
    toast('Avance guardado en este dispositivo.', 'info');
  });
  $('#restoreProgressBtn').addEventListener('click', () => {
    renderChecklistView();
    renderClosePreview();
    setStatus('Avance guardado en este dispositivo', 'info');
    toast('Avance local restaurado.', 'info');
  });
  $('#openCloseFromChecklistBtn').addEventListener('click', () => {
    state.closeRoutineId = state.checklistSectionId;
    setView('close');
  });
  $('#clearSectionBtn').addEventListener('click', () => {
    clearRoutineStorage(state.checklistSectionId);
    renderChecklistView();
    renderCloseView();
    setStatus('Checklist incompleto', 'warning');
    toast('Se limpió el avance local de esta sección.', 'warning');
  });
  $('#closeRoutine').addEventListener('change', renderClosePreview);
  $('#includePending').addEventListener('change', renderClosePreview);
  $('#resetCloseViewBtn').addEventListener('click', renderCloseView);
  $('#closeRunForm').addEventListener('submit', async (event) => {
    try {
      await submitCloseForm(event);
    } catch (error) {
      toast(error.message, 'danger');
    }
  });
  $('#reloadHistoryBtn').addEventListener('click', async () => {
    await loadHistory(true);
    renderHistory();
    toast('Historial actualizado.', 'success');
  });
  $('#loadMoreHistoryBtn').addEventListener('click', async () => {
    await loadHistory(false);
    renderHistory();
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
  $('#createBackupBtn').addEventListener('click', createBackup);
  $('#mobileMoreBtn').addEventListener('click', () => {
    const next = $('#mobileMoreMenu').hidden;
    $('#mobileMoreMenu').hidden = !next;
    $('#mobileMoreBtn').setAttribute('aria-expanded', String(next));
  });

  document.addEventListener('click', async (event) => {
    const viewButton = event.target.closest('[data-view-target]');
    if (viewButton) {
      const targetView = viewButton.dataset.viewTarget;
      if (targetView === 'admin' && !isAdmin()) return;
      if (targetView === 'close' && !canWrite()) return;
      await setView(targetView);
      return;
    }
    const routineButton = event.target.closest('[data-open-routine]');
    if (routineButton) {
      state.checklistSectionId = routineButton.dataset.openRoutine;
      state.taskSearch = '';
      $('#taskSearch').value = '';
      renderChecklistView();
      await setView('checklist');
      return;
    }
    const sectionButton = event.target.closest('[data-checklist-section]');
    if (sectionButton) {
      state.checklistSectionId = sectionButton.dataset.checklistSection;
      renderChecklistView();
      return;
    }
    const deleteButton = event.target.closest('[data-delete-run]');
    if (deleteButton) {
      await deleteRun(deleteButton.dataset.deleteRun);
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
    const moveButton = event.target.closest('[data-move-item]');
    if (moveButton) {
      await moveItem(moveButton.dataset.moveItem, moveButton.dataset.direction);
      return;
    }
    const toggleItemButton = event.target.closest('[data-toggle-item]');
    if (toggleItemButton) {
      await toggleItem(toggleItemButton.dataset.toggleItem, toggleItemButton.dataset.active === '1');
      return;
    }
    const restoreButton = event.target.closest('[data-restore-backup]');
    if (restoreButton) {
      await restoreBackup(restoreButton.dataset.restoreBackup);
      return;
    }
    if (!event.target.closest('#mobileMoreMenu') && !event.target.closest('#mobileMoreBtn')) closeMobileMenu();
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
      setStatus('Avance guardado en este dispositivo', 'info');
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-user-form]');
    if (!form) return;
    await saveUser(event);
  });
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/static/service-worker.js').catch(() => {}));
}

init();
