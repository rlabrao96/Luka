import { createClient } from "@/app/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    await supabase.auth.exchangeCodeForSession(code);

    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const res = await fetch(`${apiUrl}/auth/me`, {
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${session.access_token}`
          }
        });
        if (res.ok) {
          const user = await res.json();
          if (!user.household_id) {
            return NextResponse.redirect(`${origin}/onboarding/setup-household`);
          }
        }
      } catch (err) {
        console.error("Failed to fetch user during callback", err);
      }
    }
  }

  // Fallback or returning user
  return NextResponse.redirect(`${origin}/`);
}
