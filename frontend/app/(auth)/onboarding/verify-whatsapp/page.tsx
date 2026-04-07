"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export default function VerifyWhatsAppPage() {
  const router = useRouter();
  const { onboardingDraft, setHousehold } = useLukaStore();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [pinSent, setPinSent] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const finalizeOnboarding = async () => {
    try {
      if (onboardingDraft?.type) {
        const household = await api.createHousehold("Mi Hogar", onboardingDraft.type);
        if (household.id) {
          setHousehold(household.id);
          if (onboardingDraft.type === "group" && onboardingDraft.memberEmail) {
            try {
              await api.inviteMember(household.id);
            } catch (inviteError) {
              console.error("Member invite failed, continuing...", inviteError);
            }
          }
        }
      }
      router.push("/onboarding/connect-bank");
    } catch (e) {
      console.error("Failed to setup household:", e);
    }
  };

  const normalizePhone = (raw: string) => raw.replace(/[\s\-()]/g, "");

  const sendPin = async () => {
    setError(null);
    setIsSending(true);
    try {
      await api.sendWhatsAppPin(normalizePhone(phone));
      setPinSent(true);
      setCooldown(60);
    } catch (e: any) {
      setError(e.message || "Error al enviar el PIN");
    } finally {
      setIsSending(false);
    }
  };

  const verifyPin = async () => {
    setError(null);
    setIsVerifying(true);
    try {
      await api.verifyWhatsAppPin(normalizePhone(phone), pin);
      await finalizeOnboarding();
    } catch (e: any) {
      setError(e.message || "PIN incorrecto o expirado");
      setIsVerifying(false);
    }
  };

  const skip = async () => {
    setIsVerifying(true);
    await finalizeOnboarding();
  };

  return (
    <Card>
      <CardHeader><CardTitle>Verifica tu WhatsApp</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-luka-muted text-sm">
          Luka te enviará alertas de gastos por WhatsApp. Necesitamos verificar tu número.
        </p>
        <Input
          placeholder="+56 9 1234 5678"
          value={phone}
          onChange={e => { setPhone(e.target.value); setError(null); }}
          disabled={isSending || isVerifying}
          className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />

        {error && (
          <p className="text-sm text-red-500 font-medium">{error}</p>
        )}

        <div className="space-y-2">
          {!pinSent ? (
            <Button
              className="w-full bg-luka-primary rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              onClick={sendPin}
              disabled={isSending || !phone.trim()}
            >
              {isSending ? "Enviando..." : "Enviar PIN por WhatsApp"}
            </Button>
          ) : (
            <>
              <Input
                placeholder="Código de 6 dígitos"
                value={pin}
                onChange={e => { setPin(e.target.value); setError(null); }}
                disabled={isVerifying}
                className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <Button
                className="w-full bg-luka-primary rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                onClick={verifyPin}
                disabled={isVerifying || !pin.trim()}
              >
                {isVerifying ? "Verificando..." : "Verificar →"}
              </Button>
              <button
                onClick={sendPin}
                disabled={cooldown > 0 || isSending}
                className="w-full text-sm text-luka-primary hover:text-blue-700 text-center py-1 disabled:text-luka-muted disabled:cursor-not-allowed"
              >
                {cooldown > 0 ? `Reenviar en ${cooldown}s` : "Reenviar PIN"}
              </button>
            </>
          )}

          <button
            onClick={skip}
            disabled={isSending || isVerifying}
            className="w-full text-sm text-luka-muted hover:text-luka-dark text-center py-2 disabled:opacity-50"
          >
            {isVerifying ? "Cargando..." : "Saltar por ahora"}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
