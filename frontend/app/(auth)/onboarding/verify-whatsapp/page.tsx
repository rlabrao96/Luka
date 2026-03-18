"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

export default function VerifyWhatsAppPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [pinSent, setPinSent] = useState(false);

  const sendPin = async () => {
    // Mock the send for now until backend is implemented
    setTimeout(() => setPinSent(true), 500);
  };

  const verifyPin = async () => {
    // Mock successful verification
    router.push("/onboarding/setup-household");
  };

  return (
    <Card>
      <CardHeader><CardTitle>Verifica tu WhatsApp</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-luka-muted text-sm">
          Luka te enviará alertas de gastos por WhatsApp. Necesitamos verificar tu número.
        </p>
        <Input placeholder="+56 9 1234 5678" value={phone} onChange={e => setPhone(e.target.value)} />
        <div className="space-y-2">
          {!pinSent ? (
            <Button className="w-full bg-luka-primary" onClick={sendPin}>Enviar PIN por WhatsApp</Button>
          ) : (
            <>
              <Input placeholder="Código de 6 dígitos" value={pin} onChange={e => setPin(e.target.value)} />
              <Button className="w-full bg-luka-primary" onClick={verifyPin}>Verificar →</Button>
            </>
          )}

          <button
            onClick={() => router.push("/onboarding/setup-household")}
            className="w-full text-sm text-luka-muted hover:text-luka-dark text-center py-2"
          >
            Saltar por ahora
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
