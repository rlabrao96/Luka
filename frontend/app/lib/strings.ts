/** Capitalize the first letter of each whitespace-separated word.
 *  Matches the shape used across transaction/merchant displays:
 *  "BANCO DE CHILE" → "Banco De Chile". */
export function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
