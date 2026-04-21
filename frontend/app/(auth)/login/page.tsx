"use client";
import { createClient } from "@/app/lib/supabase/client";
import { Button } from "@/components/ui/button";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PWA_SESSION_KEY = "luka_pwa_session";
const MICROSOFT_LOGIN_ENABLED = true;

const AUTH_ERROR_COPY: Record<string, string> = {
  auth_failed: "No pudimos iniciar sesión. Intenta de nuevo.",
  no_session: "Tu sesión expiró, inicia sesión de nuevo.",
  no_code: "Falta información en el enlace. Intenta de nuevo.",
};

export default function LoginPage() {
  const router = useRouter();
  const [recovering, setRecovering] = useState(false);
  const [pending, setPending] = useState<"google" | "microsoft" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Read ?error=... via window.location so the page stays statically-prerenderable.
  // useSearchParams would require a Suspense boundary on Next 16.
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("error");
    if (code && AUTH_ERROR_COPY[code]) {
      setError(AUTH_ERROR_COPY[code]);
    }
  }, []);

  // PWA session recovery: if iOS cleared cookies but localStorage has a saved session,
  // restore it and redirect back to dashboard
  useEffect(() => {
    if (typeof window === "undefined") return;
    const isPWA = window.matchMedia("(display-mode: standalone)").matches;
    if (!isPWA) return;

    const saved = localStorage.getItem(PWA_SESSION_KEY);
    if (!saved) return;

    setRecovering(true);
    const { refresh_token } = JSON.parse(saved);
    const supabase = createClient();

    // Use refreshSession (not setSession) — works even if access token is expired
    supabase.auth.refreshSession({ refresh_token }).then(({ data, error }) => {
      if (error || !data.session) {
        // Refresh token is invalid/expired — clear it and show login normally
        localStorage.removeItem(PWA_SESSION_KEY);
        setRecovering(false);
        return;
      }
      // Update localStorage with fresh tokens
      localStorage.setItem(PWA_SESSION_KEY, JSON.stringify({
        access_token: data.session.access_token,
        refresh_token: data.session.refresh_token,
      }));
      // Session restored — full page reload to ensure middleware sees cookies
      window.location.replace("/");
    });
  }, [router]);

  // Store redirect URL (e.g. from invite flow) as cookie so server-side callback can read it.
  // MUST be in useEffect — cookie writes are side effects; running them during render
  // violates React 19 rendering rules and fires twice under Strict Mode.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get("redirect");
    if (!redirect || !redirect.startsWith("/") || redirect.startsWith("//")) return;
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `luka-post-login-redirect=${encodeURIComponent(redirect)}; path=/; max-age=600; SameSite=Lax${secure}`;
  }, []);

  // While recovering PWA session, show minimal loading state
  if (recovering) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <Image src="/logo.svg" alt="Luka" width={120} height={120} className="h-20 w-auto" priority />
          <div className="w-6 h-6 border-2 border-luka-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  const signInWithGoogle = async () => {
    if (pending) return;
    setPending("google");
    setError(null);
    const supabase = createClient();
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        scopes: "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: {
          access_type: "offline",
          prompt: "select_account",
        },
      },
    });
    if (oauthError) {
      setError("No pudimos iniciar sesión con Google. Intenta de nuevo.");
      setPending(null);
    }
  };

  const signInWithMicrosoft = async () => {
    if (pending) return;
    setPending("microsoft");
    setError(null);
    const supabase = createClient();
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "azure",
      options: {
        scopes: "openid email profile",
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (oauthError) {
      setError("No pudimos iniciar sesión con Microsoft. Intenta de nuevo.");
      setPending(null);
    }
  };

  return (
    <div className="min-h-screen flex relative bg-slate-50 lg:bg-white overflow-hidden">
      {/* ── Mobile background (hidden on desktop) ── */}
      <div 
        className="absolute inset-0 lg:hidden bg-cover bg-center"
        style={{
          backgroundImage: "url('/background.jpg')",
        }}
      >
        {/* Subtle dark gradient overlay to make things readable and stylish */}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/95 via-slate-900/40 to-slate-900/70" />
      </div>

      {/* ── Left panel: form ── */}
      <div className="flex flex-col justify-start lg:justify-center items-center w-full lg:w-1/2 px-4 pt-16 pb-10 lg:px-8 lg:py-12 relative z-20 min-h-screen lg:min-h-0 overflow-y-auto">
        
        {/* ── Mobile Top Text ── */}
        <div className="w-full max-w-sm lg:hidden z-10 text-white antialiased mt-4 mb-8 px-4 sm:px-6 flex flex-col items-center text-center">
          <h2 className="text-3xl font-bold leading-tight mb-3 drop-shadow-lg">
            Tus finanzas,<br />en un solo lugar.
          </h2>
          <p className="text-base text-slate-200/90 drop-shadow-md font-medium">
            Captura tus gastos automáticamente y coordina con otros — sin esfuerzo.
          </p>
        </div>

        <div className="w-full max-w-sm bg-white lg:bg-transparent p-8 lg:p-0 rounded-[2.5rem] lg:rounded-none shadow-2xl lg:shadow-none border border-slate-100 lg:border-none">
          {/* Logo */}
          <div className="mb-8 lg:mb-10 text-center lg:text-left">
            <div className="flex justify-center lg:justify-start">
              <Image 
                src="/logo.svg" 
                alt="Luka Logo" 
                width={300} 
                height={300} 
                className="h-40 w-auto lg:h-32"
                priority
              />
            </div>
            <p className="text-sm text-slate-500 lg:text-luka-muted mt-2 lg:mt-1 font-medium lg:font-normal">Finanzas personales y compartidas</p>
          </div>

          {/* Heading */}
          <h1 className="text-2xl font-bold text-slate-900 lg:text-luka-dark mb-2 text-center lg:text-left">Bienvenido</h1>
          <p className="text-sm text-slate-500 lg:text-luka-muted mb-8 text-center lg:text-left">
            Inicia sesión para acceder a tu dashboard financiero.
          </p>

          {error && (
            <div
              role="alert"
              aria-live="polite"
              className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {error}
            </div>
          )}

          {/* Buttons */}
          <div className="space-y-4 lg:space-y-3">
            <Button
              onClick={signInWithGoogle}
              disabled={pending !== null}
              aria-busy={pending === "google"}
              className="w-full bg-luka-primary hover:bg-blue-700 text-white font-medium h-12 lg:h-11 text-sm gap-2 rounded-xl transition-all duration-200 hover:shadow-md lg:hover:shadow-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-70"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#ffffff"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#ffffff"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#ffffff"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#ffffff"/>
              </svg>
              Continuar con Google
            </Button>

            {MICROSOFT_LOGIN_ENABLED && (
              <Button
                onClick={signInWithMicrosoft}
                variant="outline"
                disabled={pending !== null}
                aria-busy={pending === "microsoft"}
                className="w-full border-slate-200 text-slate-700 lg:text-luka-dark hover:text-slate-900 lg:hover:text-luka-dark hover:bg-slate-50 font-medium h-12 lg:h-11 text-sm gap-2 rounded-xl transition-all duration-200 hover:shadow-sm lg:hover:shadow-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-70"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <path d="M11.4 2H2v9.4h9.4V2z" fill="#F25022"/>
                  <path d="M22 2h-9.4v9.4H22V2z" fill="#7FBA00"/>
                  <path d="M11.4 12.6H2V22h9.4v-9.4z" fill="#00A4EF"/>
                  <path d="M22 12.6h-9.4V22H22v-9.4z" fill="#FFB900"/>
                </svg>
                Continuar con Microsoft
              </Button>
            )}
          </div>

          <p className="text-xs text-slate-400 lg:text-luka-muted text-center mt-8 px-2">
            Al continuar, aceptas nuestros{" "}
            <Link href="/terms" className="text-luka-primary font-medium lg:font-normal cursor-pointer hover:underline transition-all">
              Términos de uso
            </Link>{" "}
            y{" "}
            <Link href="/privacy" className="text-luka-primary font-medium lg:font-normal cursor-pointer hover:underline transition-all">
              Política de privacidad
            </Link>
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
        <div className="relative z-10 p-12 text-white xl:p-20">
          <h2 className="text-4xl xl:text-5xl font-bold leading-snug mb-4">
            Tus finanzas,<br />en un solo lugar.
          </h2>
          <p className="text-lg text-slate-300 max-w-md leading-relaxed">
            Captura tus gastos automáticamente, visualiza tus patrones y coordina con otros — todo sin esfuerzo.
          </p>
          <div className="flex gap-2 mt-8">
            <span className="w-8 h-1.5 rounded-full bg-luka-primary" />
            <span className="w-2.5 h-1.5 rounded-full bg-white/30" />
            <span className="w-2.5 h-1.5 rounded-full bg-white/30" />
          </div>
        </div>
      </div>
    </div>
  );
}
