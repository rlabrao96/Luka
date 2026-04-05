/**
 * Category → icon lookup (Spanish + English).
 * Not user-facing — used to resolve an icon when a category name matches.
 * Falls back to first letter if no match found.
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
  "Bonos": "🎯",
  "Bonus": "🎯",
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
