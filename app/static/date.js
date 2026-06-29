function pad2(value) {
  return String(value).padStart(2, '0');
}

export function localDateKey(date = new Date()) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function localTimeKey(date = new Date()) {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

export function formatDateTimeLocal(date = new Date()) {
  return {
    dateKey: localDateKey(date),
    timeKey: localTimeKey(date),
    humanDate: `${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}/${date.getFullYear()}`,
    humanTime: localTimeKey(date)
  };
}

export function monthKey(date = new Date()) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;
}

export function parseDateKey(dateKey) {
  const [year, month, day] = dateKey.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function formatDateKey(dateKey) {
  return new Intl.DateTimeFormat('es-PY', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).format(parseDateKey(dateKey));
}

export function formatMonthLabel(date) {
  return new Intl.DateTimeFormat('es-PY', { month: 'long', year: 'numeric' }).format(date);
}

export function isPastDateKey(dateKey) {
  return dateKey < localDateKey();
}
