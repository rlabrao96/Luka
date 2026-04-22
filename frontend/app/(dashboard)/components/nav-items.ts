import {
  LayoutDashboard,
  CreditCard,
  Users,
  Wallet,
  Repeat,
  Settings,
  Bell,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  /** Full label — used in Sidebar and as accessible name in BottomNav. */
  label: string;
  /** Short label — used for BottomNav tab text where space is tight. */
  shortLabel: string;
  icon: LucideIcon;
  /** When false, hide this entry in the mobile BottomNav. */
  showInBottom: boolean;
  /** When false, hide this entry in the desktop Sidebar's main nav. */
  showInSidebar: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/",              label: "Dashboard",     shortLabel: "Inicio",     icon: LayoutDashboard, showInBottom: true, showInSidebar: true },
  { href: "/transactions",  label: "Transacciones", shortLabel: "Gastos",     icon: CreditCard,      showInBottom: true, showInSidebar: true },
  { href: "/household",     label: "Compartido",    shortLabel: "Compartido", icon: Users,           showInBottom: true, showInSidebar: true },
  { href: "/budgets",       label: "Presupuesto",   shortLabel: "Presupuesto",icon: Wallet,          showInBottom: true, showInSidebar: true },
  { href: "/subscriptions", label: "Suscripciones", shortLabel: "Subs.",      icon: Repeat,          showInBottom: true, showInSidebar: true },
  // Notifications live in the BottomNav on mobile (no bell icon in the mobile
  // chrome today); on desktop the Sidebar renders a NotificationBadge at the
  // bottom of its nav list, so the main-list entry is hidden there.
  { href: "/notifications", label: "Notificaciones", shortLabel: "Notif.",    icon: Bell,            showInBottom: true, showInSidebar: false },
  { href: "/settings",      label: "Configuración", shortLabel: "Config",     icon: Settings,        showInBottom: true, showInSidebar: true },
];
