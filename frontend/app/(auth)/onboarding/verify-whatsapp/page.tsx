"use client";
import { useState } from "react";
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
  const [isSubmitting, setIsSubmitting] = useState(false);

  const finalizeOnboarding = async () => {
    try {
      setIsSubmitting(true);
      if (onboardingDraft?.type) {
        const household = await api.createHousehold("Mi Hogar", onboardingDraft.type);
        if (household.id) {
          setHousehold(household.id);
          if (onboardingDraft.type === "couple" && onboardingDraft.partnerEmail) {
            try {
              await api.invitePartner(household.id, onboardingDraft.partnerEmail);
            } catch (inviteError) {
              console.error("Partner invite failed, continuing...", inviteError);
            }
          }
        }
      }
      router.push("/onboarding/connect-bank");
    } catch (e) {
      console.error("Failed to setup household:", e);
      setIsSubmitting(false);
    }
  };

  const sendPin = async () => {
    // Mock the send for now until backend is implemented
    setTimeout(() => setPinSent(true), 500);
  };

  const verifyPin = async () => {
    // Mock successful verification
    await finalizeOnboarding();
  };

  const skip = async () => {
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
          onChange={e => setPhone(e.target.value)}
          disabled={isSubmitting}
          className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />
        <div className="space-y-2">
          {!pinSent ? (
            <Button
              className="w-full bg-luka-primary rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              onClick={sendPin}
              disabled={isSubmitting}
            >
              Enviar PIN por WhatsApp
            </Button>
          ) : (
            <>
              <Input
                placeholder="Código de 6 dígitos"
                value={pin}
                onChange={e => setPin(e.target.value)}
                disabled={isSubmitting}
                className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <Button
                className="w-full bg-luka-primary rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                onClick={verifyPin}
                disabled={isSubmitting}
              >
                {isSubmitting ? "Finalizando..." : "Verificar →"}
              </Button>
            </>
          )}

          <button
            onClick={skip}
            disabled={isSubmitting}
            className="w-full text-sm text-luka-muted hover:text-luka-dark text-center py-2 disabled:opacity-50"
          >
            {isSubmitting ? "Cargando..." : "Saltar por ahora"}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
