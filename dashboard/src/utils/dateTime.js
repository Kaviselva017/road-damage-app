const INDIA_TIMEZONE = 'Asia/Kolkata';

const DATE_FORMATTER = new Intl.DateTimeFormat('en-IN', {
  timeZone: INDIA_TIMEZONE,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('en-IN', {
  timeZone: INDIA_TIMEZONE,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

export function parseDateValue(value) {
  if (!value) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  let normalized = String(value).trim();
  if (!normalized) return null;
  normalized = normalized.replace(' ', 'T');

  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    normalized = `${normalized}T00:00:00Z`;
  } else if (!/(Z|[+-]\d{2}:\d{2})$/i.test(normalized)) {
    normalized = `${normalized}Z`;
  }

  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDate(value) {
  const parsed = parseDateValue(value);
  return parsed ? DATE_FORMATTER.format(parsed) : '--';
}

export function formatDateTime(value) {
  const parsed = parseDateValue(value);
  return parsed ? DATE_TIME_FORMATTER.format(parsed) : '--';
}
