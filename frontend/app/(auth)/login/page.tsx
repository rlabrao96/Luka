"use client";
import { createClient } from "@/app/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
    <div className="min-h-screen flex items-center justify-center bg-luka-light">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold text-luka-primary">Luka</CardTitle>
          <p className="text-luka-muted mt-1">Finanzas personales y en pareja</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button onClick={signInWithGoogle} className="w-full bg-luka-primary hover:bg-blue-700">
            Continuar con Google (Gmail)
          </Button>
          <Button onClick={signInWithMicrosoft} variant="outline" className="w-full border-luka-primary text-luka-primary">
            Continuar con Microsoft (Outlook)
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
