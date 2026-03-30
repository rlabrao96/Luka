import { createClient } from "@/app/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);

    if (error) {
      console.error("exchangeCodeForSession failed:", error.message);
      return NextResponse.redirect(`${origin}/login?error=auth_failed`);
    }

    const session = data?.session;

    if (!session) {
      console.error("No session returned after code exchange");
      return NextResponse.redirect(`${origin}/login?error=no_session`);
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    // Store Google provider tokens for Gmail API access
    if (session.provider_token) {
      try {
        await fetch(`${apiUrl}/auth/store-provider-tokens`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({
            provider_token: session.provider_token,
            provider_refresh_token: session.provider_refresh_token ?? null,
          }),
        });
      } catch (err) {
        console.error("Failed to store provider tokens", err);
      }
    }

    // Check if user needs onboarding
    try {
      const res = await fetch(`${apiUrl}/auth/me`, {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
      });
      if (res.ok) {
        const user = await res.json();
        if (!user.household_id) {
          const onboardingResponse = NextResponse.redirect(`${origin}/onboarding/setup-household`);
          onboardingResponse.cookies.set("luka-fresh-login", "1", {
            maxAge: 60,
            path: "/",
            sameSite: "lax",
            httpOnly: false,
            secure: origin.startsWith("https"),
          });
          return onboardingResponse;
        }
      }
    } catch (err) {
      console.error("Failed to fetch user during callback", err);
    }

    const response = NextResponse.redirect(`${origin}/`);
    response.cookies.set("luka-fresh-login", "1", {
      maxAge: 60,
      path: "/",
      sameSite: "lax",
      httpOnly: false,
      secure: origin.startsWith("https"),
    });
    return response;
  }

  // No code parameter — redirect to login
  return NextResponse.redirect(`${origin}/login?error=no_code`);
}
