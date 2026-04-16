/**
 * Category icon + color mapping for the budget config modal.
 *
 * Each expense category from the default seed gets a hand-picked emoji
 * and a gradient color theme for the pill background. Unknown or custom
 * categories fall back to a first-letter pill + a deterministic color
 * picked from the name hash.
 *
 * Additive-only: adding a new entry never breaks an existing one.
 */

export type CategoryPillTheme = "amber" | "green" | "pink" | "blue" | "purple";

export const PILL_GRADIENTS: Record<CategoryPillTheme, string> = {
  amber: "linear-gradient(135deg, #FEF3C7, #FDE68A)",
  green: "linear-gradient(135deg, #D1FAE5, #A7F3D0)",
  pink: "linear-gradient(135deg, #FCE7F3, #FBCFE8)",
  blue: "linear-gradient(135deg, #DBEAFE, #BFDBFE)",
  purple: "linear-gradient(135deg, #E9D5FF, #DDD6FE)",
};

type CategoryIconSpec = { emoji: string; theme: CategoryPillTheme };

// Default-seed expense categories. Keys must match the Spanish labels
// used by modules/settings and the category_preferences table.
const EXPENSE_ICONS: Record<string, CategoryIconSpec> = {
  "Supermercado": { emoji: "🛒", theme: "green" },
  "Restaurantes": { emoji: "🍽️", theme: "pink" },
  "Transporte": { emoji: "🚗", theme: "blue" },
  "Combustible": { emoji: "⛽", theme: "amber" },
  "Entretenimiento": { emoji: "🎬", theme: "purple" },
  "Salud": { emoji: "💊", theme: "pink" },
  "Educación": { emoji: "📚", theme: "blue" },
  "Servicios del hogar": { emoji: "🏠", theme: "purple" },
  "Ropa": { emoji: "👕", theme: "pink" },
  "Tecnología": { emoji: "💻", theme: "blue" },
  "Viajes": { emoji: "✈️", theme: "blue" },
  "Cuidado personal": { emoji: "💈", theme: "pink" },
  "Regalos": { emoji: "🎁", theme: "amber" },
  "Mascotas": { emoji: "🐾", theme: "amber" },
  "Suscripciones": { emoji: "🔁", theme: "purple" },
  "Seguros": { emoji: "🛡️", theme: "blue" },
  "Impuestos": { emoji: "🧾", theme: "amber" },
  "Deporte": { emoji: "🏋️", theme: "green" },
  "Niños": { emoji: "🧸", theme: "pink" },
  "Otros gastos": { emoji: "💸", theme: "purple" },
};

const THEMES: CategoryPillTheme[] = ["amber", "green", "pink", "blue", "purple"];

/**
 * Deterministic theme for an arbitrary category name.
 * Uses the sum of char codes mod 5 so the same name always resolves to
 * the same theme across sessions and users.
 */
function themeFromName(name: string): CategoryPillTheme {
  let sum = 0;
  for (let i = 0; i < name.length; i++) sum += name.charCodeAt(i);
  return THEMES[sum % THEMES.length];
}

export function getCategoryIcon(category: string): {
  emoji: string;
  theme: CategoryPillTheme;
  gradient: string;
} {
  const known = EXPENSE_ICONS[category];
  if (known) {
    return { ...known, gradient: PILL_GRADIENTS[known.theme] };
  }
  const theme = themeFromName(category);
  return {
    emoji: category.trim().charAt(0).toUpperCase() || "?",
    theme,
    gradient: PILL_GRADIENTS[theme],
  };
}
