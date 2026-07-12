"use client";
import Link from "next/link";
import { Landmark, Mail, MessageCircle, Sparkles, ArrowRight, Check } from "lucide-react";

interface FirstRunStep {
  done: boolean;
  icon: typeof Landmark;
  title: string;
  body: string;
  href: string;
  cta: string;
}

interface FirstRunCardProps {
  hasBankAccount: boolean;
  whatsappVerified: boolean;
  emailConnected: boolean;
}

/** First-run activation card (shown only until the user has real data).
 *
 * Best-practice: a guided empty state that walks the user to their first win
 * (a captured transaction) beats a blank "Sin datos aún" screen — the
 * activation moment for Luka is seeing a bank email turn into a categorized
 * transaction automatically. Steps disappear as they're completed; the whole
 * card unmounts once the first transaction lands (handled by the parent). */
export function FirstRunCard({
  hasBankAccount,
  whatsappVerified,
  emailConnected,
}: FirstRunCardProps) {
  const steps: FirstRunStep[] = [
    {
      done: emailConnected,
      icon: Mail,
      title: "Conecta tu correo",
      body: "Luka lee tus notificaciones bancarias y las convierte en transacciones — sin que muevas un dedo.",
      href: "/settings",
      cta: "Revisar conexión",
    },
    {
      done: hasBankAccount,
      icon: Landmark,
      title: "Vincula un banco (opcional)",
      body: "Conecta una cuenta para ver tus saldos y capturar movimientos al instante.",
      href: "/settings",
      cta: "Vincular banco",
    },
    {
      done: whatsappVerified,
      icon: MessageCircle,
      title: "Activa WhatsApp",
      body: "Recibe cada gasto en tiempo real y clasifícalo con un toque.",
      href: "/settings",
      cta: "Verificar número",
    },
  ];

  const completed = steps.filter((s) => s.done).length;
  const nextStep = steps.find((s) => !s.done) ?? steps[0];

  return (
    <div className="overflow-hidden rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white shadow-sm">
      <div className="p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-luka-primary/10 text-luka-primary">
            <Sparkles size={20} />
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-luka-dark">
              Empecemos con tu primer gasto capturado
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              En cuanto llegue una notificación de tu banco, Luka la clasifica
              sola y la verás aquí. Falta poco:
            </p>
          </div>
        </div>

        {/* Progress */}
        <div className="mt-4 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-luka-primary transition-all"
              style={{ width: `${(completed / steps.length) * 100}%` }}
            />
          </div>
          <span className="text-[11px] font-semibold tabular-nums text-slate-500">
            {completed}/{steps.length}
          </span>
        </div>

        {/* Steps */}
        <ul className="mt-4 space-y-2.5">
          {steps.map((step) => {
            const Icon = step.icon;
            const isNext = step.title === nextStep.title && !step.done;
            return (
              <li
                key={step.title}
                className={`flex items-start gap-3 rounded-xl border p-3 transition-colors ${
                  step.done
                    ? "border-emerald-100 bg-emerald-50/50"
                    : isNext
                      ? "border-blue-200 bg-white"
                      : "border-slate-100 bg-white/60"
                }`}
              >
                <span
                  className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                    step.done
                      ? "bg-emerald-100 text-emerald-600"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {step.done ? <Check size={15} /> : <Icon size={15} />}
                </span>
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-sm font-medium ${
                      step.done ? "text-emerald-700" : "text-luka-dark"
                    }`}
                  >
                    {step.title}
                  </p>
                  {!step.done && (
                    <p className="mt-0.5 text-xs leading-snug text-slate-500">
                      {step.body}
                    </p>
                  )}
                </div>
                {!step.done && (
                  <Link
                    href={step.href}
                    className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-lg bg-luka-primary px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-blue-700"
                  >
                    {step.cta}
                    <ArrowRight size={12} />
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
