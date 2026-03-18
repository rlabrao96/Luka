"use client";
import { createClient } from "@/app/lib/supabase/client";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const signInWithGoogle = async () => {
    const supabase = createClient();
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        scopes: "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
  };

  const signInWithMicrosoft = async () => {
    const supabase = createClient();
    await supabase.auth.signInWithOAuth({
      provider: "azure",
      options: {
        scopes: "openid email profile Mail.Read",
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
  };

  return (
    <div className="min-h-screen flex">
      {/* ── Left panel: form ── */}
      <div className="flex flex-col justify-center items-center w-full lg:w-1/2 px-8 py-12 bg-white">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="mb-10">
            <span className="text-3xl font-bold text-luka-primary tracking-tight">Luka</span>
            <p className="text-sm text-luka-muted mt-1">Finanzas personales y en pareja</p>
          </div>

          {/* Heading */}
          <h1 className="text-2xl font-bold text-luka-dark mb-2">Bienvenido</h1>
          <p className="text-sm text-luka-muted mb-8">
            Inicia sesión para acceder a tu dashboard financiero.
          </p>

          {/* Buttons */}
          <div className="space-y-3">
            <Button
              onClick={signInWithGoogle}
              className="w-full bg-luka-primary hover:bg-blue-700 text-white font-medium h-11 text-sm gap-2"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#ffffff"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#ffffff"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#ffffff"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#ffffff"/>
              </svg>
              Continuar con Google
            </Button>

            <Button
              onClick={signInWithMicrosoft}
              variant="outline"
              className="w-full border-slate-200 text-luka-dark hover:bg-slate-50 font-medium h-11 text-sm gap-2"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none">
                <path d="M11.4 2H2v9.4h9.4V2z" fill="#F25022"/>
                <path d="M22 2h-9.4v9.4H22V2z" fill="#7FBA00"/>
                <path d="M11.4 12.6H2V22h9.4v-9.4z" fill="#00A4EF"/>
                <path d="M22 12.6h-9.4V22H22v-9.4z" fill="#FFB900"/>
              </svg>
              Continuar con Microsoft
            </Button>
          </div>

          <p className="text-xs text-luka-muted text-center mt-8">
            Al continuar, aceptas nuestros{" "}
            <span className="text-luka-primary cursor-pointer hover:underline">
              Términos de uso
            </span>{" "}
            y{" "}
            <span className="text-luka-primary cursor-pointer hover:underline">
              Política de privacidad
            </span>
            .
          </p>
        </div>
      </div>

      {/* ── Right panel: Santiago background (desktop only) ── */}
      <div
        className="hidden lg:flex flex-col justify-end w-1/2 relative overflow-hidden"
        style={{
          backgroundImage: "url('/background.jpg')",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {/* Dark gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#0F172A]/90 via-[#0F172A]/40 to-transparent" />

        {/* Text content */}
        <div className="relative z-10 p-12 text-white">
          <h2 className="text-4xl font-bold leading-snug mb-3">
            Tus finanzas,<br />en un solo lugar.
          </h2>
          <p className="text-base text-slate-300 max-w-sm">
            Captura tus gastos automáticamente, visualiza tus patrones y coordina con tu pareja — todo sin esfuerzo.
          </p>
          <div className="flex gap-1.5 mt-6">
            <span className="w-6 h-1 rounded-full bg-luka-primary" />
            <span className="w-2 h-1 rounded-full bg-white/40" />
            <span className="w-2 h-1 rounded-full bg-white/40" />
          </div>
        </div>
      </div>
    </div>
  );
}
