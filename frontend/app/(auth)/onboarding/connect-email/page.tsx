"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function ConnectEmailPage() {
  const router = useRouter();
  return (
    <Card>
      <CardHeader><CardTitle>Tu correo está conectado</CardTitle></CardHeader>
      <CardContent>
        <p className="text-luka-muted mb-4">
          Luka leerá solo los correos de alertas de tu banco para registrar tus gastos automáticamente.
        </p>
        <Button className="w-full bg-luka-primary" onClick={() => router.push("/onboarding/verify-whatsapp")}>
          Continuar →
        </Button>
      </CardContent>
    </Card>
  );
}
