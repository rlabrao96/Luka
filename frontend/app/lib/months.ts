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
