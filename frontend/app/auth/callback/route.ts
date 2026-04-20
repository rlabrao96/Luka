import { createClient } from "@/app/lib/supabase/server";
import { NextResponse } from "next/server";

const FRESH_LOGIN_COOKIE_OPTS = {
  maxAge: 60,
  path: "/",
  sameSite: "lax" as const,
  httpOnly: false,
};

function setFreshLogin(response: NextResponse, origin: string) {
  response.cookies.set("luka-fresh-login", "1", {
    ...FRESH_LOGIN_COOKIE_OPTS,
    secure: origin.startsWith("https"),
  });
}

function resolveRedirect(request: Request, origin: string, fallback: string): string {
  const cookie = request.headers.get("cookie") ?? "";
  const match = cookie.match(/(?:^|; )luka-post-login-redirect=([^;]+)/);
  if (!match) return fallback;
  try {
    const raw = decodeURIComponent(match[1]);
    // Only allow same-origin relative paths; reject protocol-relative (//evil.com)
    // and absolute URLs to avoid open-redirect into phishing pages.
    if (raw.startsWith("/") && !raw.startsWith("//")) {
      return `${origin}${raw}`;
    }
  } catch {
    // fall through
  }
  return fallback;
}

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (!code) {
    return NextResponse.redirect(`${origin}/login?error=no_code`);
  }

  const supabase = await createClient();
  const { data, error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    console.error("exchangeCodeForSession failed:", error.message);
    return NextResponse.redirect(`${origin}/login?error=auth_failed`);
  }

  const session = data?.session;
  if (!session) {
    await supabase.auth.signOut();
    return NextResponse.redirect(`${origin}/login?error=no_session`);
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const authHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.access_token}`,
  };

  // Fire /auth/me in parallel with provider-token storage. setup-email-watch
  // talks to Gmail and routinely takes 1-3s — detach it from the critical
  // path so the browser can redirect immediately.
  const mePromise = fetch(`${apiUrl}/auth/me`, { headers: authHeaders });

  if (session.provider_token) {
    const storeTokens = fetch(`${apiUrl}/auth/store-provider-tokens`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        provider_token: session.provider_token,
        provider_refresh_token: session.provider_refresh_token ?? null,
      }),
    });
    // Await the token store (the watch setup depends on it), but detach the
    // watch itself — the backend is idempotent on retry and the frontend can
    // re-trigger if needed.
    storeTokens
      .then((res) => {
        if (!res.ok) return;
        void fetch(`${apiUrl}/auth/setup-email-watch`, {
          method: "POST",
          headers: authHeaders,
        }).catch((err) => console.error("setup-email-watch (async) failed", err));
      })
      .catch((err) => console.error("store-provider-tokens failed", err));
  }

  let targetPath = "/";
  try {
    const res = await mePromise;
    if (res.ok) {
      const user = await res.json();
      if (!user.household_id) {
        targetPath = "/onboarding/setup-household";
      }
    } else {
      console.error("/auth/me failed during callback:", res.status);
    }
  } catch (err) {
    console.error("Failed to fetch user during callback", err);
  }

  const fallback = `${origin}${targetPath}`;
  const redirectTarget =
    targetPath === "/" ? resolveRedirect(request, origin, fallback) : fallback;
  const response = NextResponse.redirect(redirectTarget);
  setFreshLogin(response, origin);
  response.cookies.set("luka-post-login-redirect", "", { maxAge: 0, path: "/" });
  return response;
}
