"use client";

import { usePathname } from "next/navigation";
import { StoreInitializer } from "@/app/(dashboard)/components/StoreInitializer";

const STEPS = [
  { label: "Hogar", href: "/onboarding/setup-household" },
  { label: "WhatsApp", href: "/onboarding/verify-whatsapp" },
  { label: "Banco", href: "/onboarding/connect-bank" },
];

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div 
      className="min-h-screen flex flex-col items-center justify-center p-4 relative"
      style={{
        backgroundImage: "url('/background.jpg')",
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <StoreInitializer />
      {/* Lighter overlay to keep the background HD but ensure contrast */}
      <div className="absolute inset-0 bg-[#0F172A]/50" />

      {/* Glassmorphism box container for the content */}
      <div className="w-full max-w-lg z-10 relative bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-6 shadow-2xl">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Nuevo Usuario</h1>
          <p className="text-white/80 text-sm">Configuración inicial de tu cuenta</p>
        </div>

        <div className="flex justify-center items-center gap-2 mb-8">
          {STEPS.map((step, i) => {
            const isActive = pathname === step.href;
            const currentIndex = STEPS.findIndex(s => s.href === pathname);
            // Default to first step if match not found (e.g. wildcard)
            const activeIndex = currentIndex === -1 ? 0 : currentIndex;
            const isPast = activeIndex > i;

            return (
              <div key={step.label} className="flex items-center gap-2">
                <div 
                  className={`w-8 h-8 rounded-full flex items-center justify-center font-bold shadow-md transition-all duration-300 ${
                    isActive 
                      ? "bg-white text-luka-primary ring-4 ring-white/40 scale-110" 
                      : isPast
                      ? "bg-luka-primary text-white"
                      : "bg-white/20 text-white/50"
                  }`}
                >
                  {i + 1}
                </div>
                <span className={`text-sm hidden sm:block font-medium drop-shadow-sm transition-colors duration-300 ${
                  isActive ? "text-white font-bold" : isPast ? "text-white/90" : "text-white/50"
                }`}>
                  {step.label}
                </span>
                {i < STEPS.length - 1 && (
                  <div className={`w-8 h-[2px] rounded-full transition-colors duration-300 ${
                    isPast ? "bg-luka-primary" : "bg-white/20"
                  }`} />
                )}
              </div>
            );
          })}
        </div>
        
        {children}
      </div>
    </div>
  );
}
