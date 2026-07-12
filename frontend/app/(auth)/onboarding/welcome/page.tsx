"use client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Mail, MessageCircle, Users } from "lucide-react";

const VALUE_POINTS = [
  {
    icon: Mail,
    title: "Captura automática",
    body: "Luka lee tus notificaciones bancarias y las convierte en transacciones categorizadas — sin que ingreses nada a mano.",
  },
  {
    icon: MessageCircle,
    title: "Alertas por WhatsApp",
    body: "Recibe cada gasto en el momento y clasifícalo con un solo toque, donde sea que estés.",
  },
  {
    icon: Users,
    title: "Gastos compartidos, claros",
    body: "Lleva la cuenta de lo que aporta cada quien en pareja o grupo — sin planillas ni discusiones.",
  },
];

/** Value-first onboarding step (best practice: show what the product does
 *  before asking for setup / sensitive data). No credentials requested here —
 *  just a preview of the aha-moment, then a single CTA into setup. */
export default function OnboardingWelcomePage() {
  const router = useRouter();
  return (
    <div>
      <div className="mb-5 text-center">
        <h2 className="text-xl font-bold text-white">Tus finanzas, sin esfuerzo</h2>
        <p className="mt-1 text-sm text-white/80">
          Esto es lo que Luka hará por ti — configúralo en menos de un minuto.
        </p>
      </div>

      <ul className="space-y-3">
        {VALUE_POINTS.map(({ icon: Icon, title, body }) => (
          <li
            key={title}
            className="flex items-start gap-3 rounded-xl border border-white/20 bg-white/10 p-3.5 backdrop-blur-sm"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/20 text-white">
              <Icon size={18} />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">{title}</p>
              <p className="mt-0.5 text-xs leading-snug text-white/75">{body}</p>
            </div>
          </li>
        ))}
      </ul>

      <Button
        onClick={() => router.push("/onboarding/setup-household")}
        className="mt-6 h-11 w-full bg-white text-luka-primary hover:bg-white/90"
      >
        Empezar
      </Button>
      <p className="mt-3 text-center text-[11px] text-white/60">
        No te pediremos datos bancarios sensibles. Tú decides qué conectar.
      </p>
    </div>
  );
}
