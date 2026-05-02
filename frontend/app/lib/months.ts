// frontend/app/lib/months.ts
//
// Single source of truth for the month-picker data layer. All three
// month-picker surfaces (Dashboard MonthSelector, Household page, Budgets
// page) derive their options and parse/serialize keys through here.

export type MonthKey = string; // "YYYY-MM"

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function monthKey(d: Date): MonthKey {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function dateFromMonthKey(key: MonthKey): Date {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, 1);
}

export function currentMonthKey(): MonthKey {
  return monthKey(new Date());
}

/** N most-recent months, most-recent first. Default N = 12 covers a full year
 *  so budgets/household users can step back without hitting an arbitrary 6-
 *  month wall. Labels are localized via Intl, with the first letter
 *  capitalized to match the rest of Luka's copy. */
export function getLastNMonths(
  locale: string,
  count = 12,
  format: Intl.DateTimeFormatOptions = { month: "short", year: "numeric" },
): { key: MonthKey; label: string }[] {
  const now = new Date();
  const options: { key: MonthKey; label: string }[] = [];
  for (let i = 0; i < count; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    options.push({
      key: monthKey(d),
      label: capitalize(d.toLocaleDateString(locale, format)),
    });
  }
  return options;
}

// Lowercase Spanish month abbreviations — match the rest of Luka's copy
// (e.g. "1 — 7 may 2026"). Kept here so the trip card and any future date-
// range card share a single source of truth.
const SPANISH_MONTHS_SHORT = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "sep", "oct", "nov", "dic",
];

/**
 * Compact Spanish date range, e.g.
 *   - same month + year:   "1 — 7 may 2026"
 *   - different months:    "28 abr — 4 may 2026"
 *   - different years:     "30 dic 2025 — 5 ene 2026"
 *
 * Inputs are ISO date strings ("YYYY-MM-DD"). Anchored at local midnight to
 * avoid TZ-shifted off-by-one days when the user's TZ is west of UTC.
 */
export function formatTripDateRange(startISO: string, endISO: string): string {
  const start = new Date(startISO + "T00:00:00");
  const end = new Date(endISO + "T00:00:00");
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return `${startISO} — ${endISO}`;
  }
  const sM = SPANISH_MONTHS_SHORT[start.getMonth()];
  const eM = SPANISH_MONTHS_SHORT[end.getMonth()];
  const sY = start.getFullYear();
  const eY = end.getFullYear();
  if (sY !== eY) {
    return `${start.getDate()} ${sM} ${sY} — ${end.getDate()} ${eM} ${eY}`;
  }
  if (sM !== eM) {
    return `${start.getDate()} ${sM} — ${end.getDate()} ${eM} ${eY}`;
  }
  return `${start.getDate()} — ${end.getDate()} ${sM} ${sY}`;
}
