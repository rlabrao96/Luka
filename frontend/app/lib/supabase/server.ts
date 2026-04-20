import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { withDurableCookie } from "./cookieOptions";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cs) =>
          cs.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, withDurableCookie(options))
          ),
      },
    }
  );
}
