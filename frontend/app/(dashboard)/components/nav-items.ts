import {
  LayoutDashboard,
  CreditCard,
  Users,
  Wallet,
  Repeat,
  Settings,
  Bell,
  Plane,
  type LucideIcon,
} from "lucide-react";

export type NavSection = "primary" | "more";

export interface NavItem {
  href: string;
  /** Full label — used in Sidebar, BottomSheet, and as accessible name. */
  label: string;
  /** Short label used for BottomNav tab text where space is tight. */
  shortLabel: string;
  /** Sub-copy for the Más bottom-sheet row. */
  description: string;
  icon: LucideIcon;
  /** Which mobile slot — `primary` = first-class BottomNav tab;
   *  `more` = surfaced from the Más overflow sheet. */
  section: NavSection;
  /** When false, hide this entry in the desktop Sidebar's main nav. */
  showInSidebar: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    shortLabel: "Inicio",
    description: "Resumen financiero del mes",
    icon: LayoutDashboard,
    section: "primary",
    showInSidebar: true,
  },
  {
    href: "/transactions",
    label: "Transacciones",
    shortLabel: "Gastos",
    description: "Historial de movimientos",
    icon: CreditCard,
    section: "primary",
    showInSidebar: true,
  },
  {
    href: "/budgets",
    label: "Presupuesto",
    shortLabel: "Plan",
    description: "Control de ingresos y gastos",
    icon: Wallet,
    section: "primary",
    showInSidebar: true,
  },
  {
    href: "/notifications",
    label: "Notificaciones",
    shortLabel: "Notif.",
    description: "Alertas y actividad reciente",
    icon: Bell,
    section: "primary",
    // Sidebar renders a dedicated NotificationBadge; don't duplicate.
    showInSidebar: false,
  },
  // ── Más overflow ────────────────────────────────────────
  {
    href: "/household",
    label: "Compartido",
    shortLabel: "Compartido",
    description: "Gastos del grupo y balances",
    icon: Users,
    section: "more",
    showInSidebar: true,
  },
  {
    href: "/subscriptions",
    label: "Suscripciones",
    shortLabel: "Subs.",
    description: "Gastos recurrentes detectados",
    icon: Repeat,
    section: "more",
    showInSidebar: true,
  },
  {
    href: "/viajes",
    label: "Viajes",
    shortLabel: "Viajes",
    description: "Gastos compartidos por viaje",
    icon: Plane,
    section: "more",
    showInSidebar: true,
  },
  {
    href: "/settings",
    label: "Configuración",
    shortLabel: "Config",
    description: "Cuenta, monedas y preferencias",
    icon: Settings,
    section: "more",
    showInSidebar: true,
  },
];

/**
 * Filter NAV_ITEMS based on per-user feature flags. Sidebar/BottomNav consumers
 * call this with the current user's flags so flag-gated entries (e.g. Viajes)
 * stay hidden until the flag is enabled. Keeps NAV_ITEMS as a static, declarative
 * source of truth — the gate lives at consume time, not in the data layer.
 */
export function visibleNavItems(opts: {
  featureTripsEnabled: boolean;
}): NavItem[] {
  return NAV_ITEMS.filter((item) => {
    if (item.href === "/viajes" && !opts.featureTripsEnabled) return false;
    return true;
  });
}
