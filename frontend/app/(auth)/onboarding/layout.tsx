const STEPS = [
  { label: "Correo", href: "/onboarding/connect-email" },
  { label: "WhatsApp", href: "/onboarding/verify-whatsapp" },
  { label: "Hogar", href: "/onboarding/setup-household" },
  { label: "Banco", href: "/onboarding/connect-bank" },
];

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div 
      className="min-h-screen flex flex-col items-center justify-center p-4 relative"
      style={{
        backgroundImage: "url('/background.jpg')",
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      {/* Dark overlay so the white card pops out */}
      <div className="absolute inset-0 bg-[#0F172A]/60 backdrop-blur-[2px]" />

      <div className="w-full max-w-lg z-10 relative">
        <h1 className="text-3xl font-bold text-white tracking-tight text-center mb-2">Luka</h1>
        <div className="flex justify-center gap-2 mb-8">
          {STEPS.map((step, i) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-luka-primary text-white text-xs flex items-center justify-center font-bold shadow-md">
                {i + 1}
              </div>
              <span className="text-sm text-white/90 hidden sm:block font-medium drop-shadow-sm">{step.label}</span>
              {i < STEPS.length - 1 && <div className="w-6 h-px bg-white/40" />}
            </div>
          ))}
        </div>
        {children}
      </div>
    </div>
  );
}
