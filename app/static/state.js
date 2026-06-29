export const VIEW_META = {
  home: { eyebrow: 'Inicio', title: 'Resumen local' },
  checklist: { eyebrow: 'Checklist', title: 'Checklist por seccion' },
  close: { eyebrow: 'Cierre', title: 'Generar cierre' },
  history: { eyebrow: 'Historial', title: 'Cierres guardados' },
  calendar: { eyebrow: 'Calendario', title: 'Actividad mensual' },
  admin: { eyebrow: 'Administracion', title: 'Panel admin' }
};

export const ROLE_LABELS = {
  admin: 'Administrador',
  usuario: 'Usuario',
  solo_lectura: 'Solo lectura'
};

export const state = {
  user: null,
  routines: [],
  categories: [],
  roles: [],
  users: [],
  adminItems: [],
  backups: [],
  activity: [],
  history: [],
  historyOffset: 0,
  historyHasMore: false,
  calendarDate: new Date(),
  selectedCalendarDate: null,
  calendarReports: {},
  view: 'home',
  checklistSectionId: null,
  closeRoutineId: null,
  adminSectionId: null,
  taskSearch: '',
  showInactiveItems: false,
  editingItemId: null,
  lastRun: null,
  statusMessage: '',
  statusTone: 'info'
};
