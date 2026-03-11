const STEPS = [
  { label: "Correo", href: "/onboarding/connect-email" },
  { label: "WhatsApp", href: "/onboarding/verify-whatsapp" },
  { label: "Hogar", href: "/onboarding/setup-household" },
  { label: "Banco", href: "/onboarding/connect-bank" },
];

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-luka-light flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <h1 className="text-2xl font-bold text-luka-primary text-center mb-2">Luka</h1>
        <div className="flex justify-center gap-2 mb-8">
          {STEPS.map((step, i) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-luka-primary text-white text-xs flex items-center justify-center font-bold">
                {i + 1}
              </div>
              <span className="text-sm text-luka-muted hidden sm:block">{step.label}</span>
              {i < STEPS.length - 1 && <div className="w-6 h-px bg-luka-primary/30" />}
            </div>
          ))}
        </div>
        {children}
      </div>
    </div>
  );
}
