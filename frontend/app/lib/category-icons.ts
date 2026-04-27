/**
 * Category → icon lookup (Spanish + English).
 * Not user-facing — used to resolve an icon when a category name matches.
 * Falls back to first letter if no match found.
 *
 * Canonical seed-default category list lives at
 * `backend/modules/settings/service.py::_DEFAULT_CATEGORIES`. Every entry in
 * that list MUST resolve to an emoji here (otherwise the dashboard renders an
 * ugly initial). When new defaults are added there, mirror them in this map.
 */

const CATEGORY_ICON_MAP: Record<string, string> = {
  // ── Food & Drink ──
  "Alimentacion": "🍽️",
  "Alimentación": "🍽️",
  "Food": "🍽️",
  "Food & Drink": "🍽️",
  "Restaurantes": "🍽️",
  "Restaurants": "🍽️",
  "Comida rapida": "🍔",
  "Fast Food": "🍔",
  "Cafeteria": "☕",
  "Coffee": "☕",
  "Café": "☕",
  "Panaderia": "🥐",
  "Bakery": "🥐",
  "Bar": "🍺",
  "Bars": "🍺",
  "Delivery": "📦",

  // ── Groceries ──
  "Supermercado": "🛒",
  "Groceries": "🛒",
  "Grocery": "🛒",
  "Mercado": "🛒",
  "Almacen": "🏪",

  // ── Transport ──
  "Transporte": "🚗",
  "Transportation": "🚗",
  "Transport": "🚗",
  "Uber": "🚗",
  "Taxi": "🚕",
  "Metro": "🚇",
  "Bus": "🚌",
  "Estacionamiento": "🅿️",
  "Parking": "🅿️",
  "Peaje": "🛣️",
  "Tolls": "🛣️",

  // ── Fuel ──
  "Combustible": "⛽",
  "Fuel": "⛽",
  "Gas": "⛽",
  "Gasolina": "⛽",
  "Bencina": "⛽",

  // ── Housing ──
  "Hogar": "🏠",
  "Home": "🏠",
  "Housing": "🏠",
  "Arriendo": "🏠",
  "Rent": "🏠",
  "Alquiler": "🏠",
  "Hipoteca": "🏦",
  "Mortgage": "🏦",
  "Arriendo/Hipoteca": "🏠",
  "Muebles": "🛋️",
  "Furniture": "🛋️",
  "Decoracion": "🖼️",
  "Decoración": "🖼️",
  "Limpieza": "🧹",
  "Cleaning": "🧹",
  "Reparaciones": "🔧",
  "Repairs": "🔧",
  "Mantenimiento": "🔧",
  "Maintenance": "🔧",

  // ── Utilities ──
  "Servicios": "💡",
  "Utilities": "💡",
  "Cuentas": "🧾",
  "Bills": "🧾",
  "Electricidad": "⚡",
  "Electricity": "⚡",
  "Agua": "💧",
  "Water": "💧",
  "Internet": "🌐",
  "Telefono": "📱",
  "Teléfono": "📱",
  "Phone": "📱",
  "Cable": "📺",
  "TV": "📺",

  // ── Health ──
  "Salud": "🏥",
  "Health": "🏥",
  "Healthcare": "🏥",
  "Medico": "👨‍⚕️",
  "Doctor": "👨‍⚕️",
  "Dentista": "🦷",
  "Dental": "🦷",
  "Farmacia": "💊",
  "Pharmacy": "💊",
  "Gimnasio": "🏋️",
  "Gym": "🏋️",
  "Fitness": "🏋️",
  "Deporte": "⚽",
  "Deportes": "⚽",
  "Sport": "⚽",
  "Sports": "⚽",
  "Bienestar": "🧘",
  "Wellness": "🧘",

  // ── Insurance ──
  "Seguros": "🛡️",
  "Insurance": "🛡️",
  "Seguro auto": "🚗",
  "Auto Insurance": "🚗",
  "Seguro salud": "🏥",
  "Health Insurance": "🏥",

  // ── Education ──
  "Educacion": "📚",
  "Educación": "📚",
  "Education": "📚",
  "Colegio": "🎓",
  "School": "🎓",
  "Universidad": "🎓",
  "University": "🎓",
  "Cursos": "📖",
  "Courses": "📖",
  "Libros": "📕",
  "Books": "📕",

  // ── Entertainment ──
  "Entretenimiento": "🎬",
  "Entertainment": "🎬",
  "Cine": "🎬",
  "Movies": "🎬",
  "Musica": "🎵",
  "Music": "🎵",
  "Streaming": "📺",
  "Suscripciones": "🔄",
  "Subscriptions": "🔄",
  "Juegos": "🎮",
  "Games": "🎮",
  "Gaming": "🎮",
  "Hobbies": "🎨",
  "Pasatiempos": "🎨",

  // ── Shopping ──
  "Ropa": "👕",
  "Clothing": "👕",
  "Clothes": "👕",
  "Moda": "👗",
  "Fashion": "👗",
  "Zapatos": "👟",
  "Shoes": "👟",
  "Accesorios": "👜",
  "Accessories": "👜",
  "Compras": "🛍️",
  "Shopping": "🛍️",
  "Regalos": "🎁",
  "Gifts": "🎁",

  // ── Technology ──
  "Tecnologia": "💻",
  "Tecnología": "💻",
  "Technology": "💻",
  "Electronics": "📱",
  "Electronica": "📱",
  "Software": "💻",
  "Apps": "📲",

  // ── Travel ──
  "Viajes": "✈️",
  "Travel": "✈️",
  "Vuelos": "✈️",
  "Flights": "✈️",
  "Hotel": "🏨",
  "Hotels": "🏨",
  "Alojamiento": "🏨",
  "Accommodation": "🏨",
  "Vacaciones": "🏖️",
  "Vacation": "🏖️",

  // ── Pets ──
  "Mascotas": "🐾",
  "Pets": "🐾",
  "Veterinario": "🐾",
  "Vet": "🐾",

  // ── Kids ──
  "Hijos": "👶",
  "Kids": "👶",
  "Children": "👶",
  "Guarderia": "🧒",
  "Daycare": "🧒",
  "Childcare": "🧒",

  // ── Personal Care ──
  "Cuidado personal": "💇",
  "Personal Care": "💇",
  "Peluqueria": "💇",
  "Haircut": "💇",
  "Cosmeticos": "💄",
  "Beauty": "💄",

  // ── Financial ──
  "Impuestos": "🏛️",
  "Taxes": "🏛️",
  "Comisiones": "🏦",
  "Fees": "🏦",
  "Bank Fees": "🏦",
  "Intereses": "📊",
  "Interest": "📊",
  "Inversiones": "📈",
  "Investments": "📈",
  "Ahorro": "🐷",
  "Savings": "🐷",
  "Deuda": "💳",
  "Debt": "💳",
  "Credito": "💳",
  "Credit": "💳",
  "Transferencia": "🔄",
  "Transfer": "🔄",
  "Transfers": "🔄",

  // ── Income ──
  "Sueldo": "💰",
  "Salary": "💰",
  "Ingreso": "💰",
  "Income": "💰",
  "Freelance": "💼",
  "Bono": "🎯",
  "Bonos": "🎯",
  "Bonus": "🎯",
  "Deuda pendiente": "💳",
  "Otros ingresos": "💵",
  "Other Income": "💵",
  "Transferencia de terceros": "🔄",
  "Third-party Transfer": "🔄",
  "Dividendos": "📊",
  "Dividends": "📊",
  "Reembolso": "↩️",
  "Refund": "↩️",
  "Venta": "🏷️",
  "Sale": "🏷️",
  "Arriendo recibido": "🏠",
  "Rental Income": "🏠",
  "Propinas": "💵",
  "Tips": "💵",

  // ── Charity ──
  "Donaciones": "❤️",
  "Donations": "❤️",
  "Charity": "❤️",
  "Caridad": "❤️",

  // ── Catch-all ──
  "Otros": "📋",
  "Other": "📋",
  "Miscellaneous": "📋",
  "Varios": "📋",
  "General": "📋",
};

/**
 * Get icon for a category name. Case-insensitive lookup.
 * Returns the emoji if found, or null if no match.
 */
export function getCategoryIcon(category: string): string | null {
  // Direct match
  if (CATEGORY_ICON_MAP[category]) return CATEGORY_ICON_MAP[category];

  // Case-insensitive match
  const lower = category.toLowerCase();
  for (const [key, icon] of Object.entries(CATEGORY_ICON_MAP)) {
    if (key.toLowerCase() === lower) return icon;
  }

  return null;
}

/**
 * Get icon for a category, falling back to the first letter.
 */
export function getCategoryIconOrInitial(category: string): { icon: string; isEmoji: boolean } {
  const emoji = getCategoryIcon(category);
  if (emoji) return { icon: emoji, isEmoji: true };
  return { icon: category.charAt(0).toUpperCase(), isEmoji: false };
}

// ────────────────────────────────────────────────────────────
// Pill themes — used by the budget config modal (Tasks 11 & 12)
// ────────────────────────────────────────────────────────────

export type CategoryPillTheme = "amber" | "green" | "pink" | "blue" | "purple";

export const PILL_GRADIENTS: Record<CategoryPillTheme, string> = {
  amber: "linear-gradient(135deg, #FEF3C7, #FDE68A)",
  green: "linear-gradient(135deg, #D1FAE5, #A7F3D0)",
  pink: "linear-gradient(135deg, #FCE7F3, #FBCFE8)",
  blue: "linear-gradient(135deg, #DBEAFE, #BFDBFE)",
  purple: "linear-gradient(135deg, #E9D5FF, #DDD6FE)",
};

// Hand-picked themes for default-seed expense categories.
// Emoji lookup is delegated to the existing CATEGORY_ICON_MAP (which
// also covers English labels and historical Spanish variants), so the
// same icon is used here as in MerchantCard.
const CATEGORY_THEMES: Record<string, CategoryPillTheme> = {
  "Supermercado": "green",
  "Restaurantes": "pink",
  "Transporte": "blue",
  "Combustible": "amber",
  "Entretenimiento": "purple",
  "Salud": "pink",
  "Educación": "blue",
  "Servicios del hogar": "purple",
  "Ropa": "pink",
  "Tecnología": "blue",
  "Viajes": "blue",
  "Cuidado personal": "pink",
  "Regalos": "amber",
  "Mascotas": "amber",
  "Suscripciones": "purple",
  "Seguros": "blue",
  "Impuestos": "amber",
  "Deporte": "green",
  "Niños": "pink",
  "Otros gastos": "purple",
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

/**
 * Pill descriptor for the budget config modal: emoji + theme + gradient.
 * - Emoji comes from the shared getCategoryIcon (which already covers ~200
 *   Spanish + English category labels), falling back to the first letter of
 *   the category name.
 * - Theme comes from the hand-picked CATEGORY_THEMES map for default-seed
 *   categories, or a deterministic hash for custom/unknown categories.
 *
 * This wraps getCategoryIcon (which returns string | null) with the
 * richer shape the category caps editor needs for its visual pills.
 */
export function getCategoryPill(category: string): {
  emoji: string;
  theme: CategoryPillTheme;
  gradient: string;
} {
  const emoji =
    getCategoryIcon(category) ??
    (category.trim().charAt(0).toUpperCase() || "?");
  const theme = CATEGORY_THEMES[category] ?? themeFromName(category);
  return {
    emoji,
    theme,
    gradient: PILL_GRADIENTS[theme],
  };
}
