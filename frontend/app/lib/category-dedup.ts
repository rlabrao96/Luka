// Pure helpers for fuzzy de-duplication of category names on add.
//
// Goals:
//   - Block exact normalized duplicates ("DEPORTE  " == "Deporte").
//   - Surface near-matches (Levenshtein <= 2) so users don't introduce
//     typos like "televecion" or "Sueldoo".
//
// No React, no I/O — fully unit-testable shape.

// Combining-mark range used to strip accents after NFD decomposition.
const COMBINING_MARKS = /[̀-ͯ]/g;

/**
 * Sentence-case a category name to match the seed-default convention
 * (`Otros ingresos`, `Arriendo/Hipoteca`, `Transferencia de terceros`).
 *
 * Lowercases the whole string, then uppercases the first letter and the
 * first letter after each `/` separator. Preserves Spanish lowercase
 * particles in multi-word names; capitalizes both halves of compound
 * names like `Arriendo/Hipoteca`.
 */
export function toCategoryCase(s: string): string {
  const trimmed = s.trim();
  if (!trimmed) return trimmed;
  return trimmed
    .toLowerCase()
    .replace(/(^|\/)(\p{L})/gu, (_, sep, ch: string) => sep + ch.toUpperCase());
}

/**
 * Normalize a category name for comparison.
 *
 * Steps: trim → lowercase → NFD-strip accents → collapse internal whitespace.
 * Idempotent. Plural collapse is intentionally NOT done here (it's done
 * inside `findDuplicate`) so this stays a stable canonicalization.
 */
export function normalize(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(COMBINING_MARKS, "")
    .replace(/\s+/g, " ");
}

/**
 * Standard DP Levenshtein distance with an early-exit optimization:
 * if the lengths differ by more than `maxDistance`, we return Infinity
 * immediately since no edit script can bridge that gap.
 */
export function levenshtein(a: string, b: string, maxDistance = Infinity): number {
  if (a === b) return 0;
  const la = a.length;
  const lb = b.length;
  if (la === 0) return lb;
  if (lb === 0) return la;
  if (Math.abs(la - lb) > maxDistance) return Infinity;

  // Two rolling rows; O(min(la, lb)) memory.
  let prev: number[] = new Array(lb + 1);
  let curr: number[] = new Array(lb + 1);
  for (let j = 0; j <= lb; j++) prev[j] = j;

  for (let i = 1; i <= la; i++) {
    curr[0] = i;
    let rowMin = curr[0];
    for (let j = 1; j <= lb; j++) {
      const cost = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
      curr[j] = Math.min(
        prev[j] + 1,        // deletion
        curr[j - 1] + 1,    // insertion
        prev[j - 1] + cost, // substitution
      );
      if (curr[j] < rowMin) rowMin = curr[j];
    }
    if (rowMin > maxDistance) return Infinity;
    [prev, curr] = [curr, prev];
  }
  return prev[lb];
}

function dropTrailingS(s: string): string {
  return s.length > 4 && s.endsWith("s") ? s.slice(0, -1) : s;
}

export type DupResult =
  | { kind: "none" }
  | { kind: "exact"; canonical: string }
  | { kind: "near"; canonical: string };

/**
 * Decide whether `name` collides with an entry in `existing`.
 *
 *   - "exact":  normalized form matches (also matches across naive plural,
 *               i.e. "deportes" vs "Deporte" both >4 chars).
 *   - "near":   Levenshtein <= 2 against normalized existing entry
 *               (<= 1 if input is short, length <= 5).
 *   - "none":   submit normally.
 *
 * `existing` should be the list scoped to the same category_type as the
 * one being added. The returned `canonical` is the original-cased name
 * from `existing` so the UI can show it back to the user.
 */
export function findDuplicate(name: string, existing: string[]): DupResult {
  const target = normalize(name);
  if (!target) return { kind: "none" };
  const targetSingular = dropTrailingS(target);

  // Pass 1: exact (with naive-plural collapse on both sides).
  for (const c of existing) {
    const n = normalize(c);
    if (!n) continue;
    if (n === target || n === targetSingular) {
      return { kind: "exact", canonical: c };
    }
    const nSingular = dropTrailingS(n);
    if (nSingular === target || nSingular === targetSingular) {
      return { kind: "exact", canonical: c };
    }
  }

  // Pass 2: near match. Tighter threshold for short inputs to avoid
  // false positives like "Casa" → "Cosa".
  const threshold = target.length <= 5 ? 1 : 2;
  let best: { d: number; canonical: string } | null = null;
  for (const c of existing) {
    const n = normalize(c);
    if (!n) continue;
    const d = levenshtein(target, n, threshold);
    if (d <= threshold && (!best || d < best.d)) {
      best = { d, canonical: c };
    }
  }
  if (best) return { kind: "near", canonical: best.canonical };
  return { kind: "none" };
}
