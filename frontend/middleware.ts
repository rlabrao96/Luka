import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { withDurableCookie } from "@/app/lib/supabase/cookieOptions";

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            const durable = withDurableCookie(options);
            request.cookies.set(name, value);
            supabaseResponse.cookies.set(name, value, durable);
          });
        },
      },
    }
  );

  // getClaims() verifies the JWT signature locally against the cached JWKS
  // (fast; no Auth server round trip once migrated to asymmetric keys).
  // During the legacy HS256 window it falls back to the Auth server.
  let hasValidSession = false;
  try {
    const { data } = await supabase.auth.getClaims();
    hasValidSession = Boolean(data?.claims?.sub);
  } catch {
    hasValidSession = false;
  }

  const { pathname } = request.nextUrl;
  const isPublic =
    pathname.startsWith("/login") ||
    pathname.startsWith("/auth/") ||
    pathname.startsWith("/onboarding") ||
    pathname.startsWith("/invite/") ||
    pathname.startsWith("/privacy") ||
    pathname.startsWith("/terms") ||
    pathname.startsWith("/data-deletion");

  if (!hasValidSession && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
