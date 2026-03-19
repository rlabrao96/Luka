"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

import { useLukaStore } from "@/app/lib/store";

export default function SetupHouseholdPage() {
  const router = useRouter();
  const setOnboardingDraft = useLukaStore((s) => s.setOnboardingDraft);
  const draft = useLukaStore((s) => s.onboardingDraft);

  const [type, setType] = useState<"individual" | "couple" | null>(draft?.type || null);
  const [partnerEmail, setPartnerEmail] = useState(draft?.partnerEmail || "");

  const nextStep = () => {
    setOnboardingDraft({ type, partnerEmail });
    router.push("/onboarding/verify-whatsapp");
  };

  return (
    <Card className="w-full shadow-sm">
      <CardHeader><CardTitle className="text-luka-dark">¿Cómo usarás Luka?</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <Button variant={type === "individual" ? "default" : "outline"}
          className="w-full" onClick={() => setType("individual")}>
          Solo — quiero controlar mis gastos
        </Button>
        <Button variant={type === "couple" ? "default" : "outline"}
          className="w-full" onClick={() => setType("couple")}>
          En pareja — compartir con mi pareja
        </Button>
        {type === "couple" && (
          <Input placeholder="Email de tu pareja" value={partnerEmail}
            onChange={e => setPartnerEmail(e.target.value)} />
        )}
        {type && (
          <Button 
            className="w-full bg-luka-primary text-white hover:bg-blue-700" 
            onClick={nextStep}
          >
            Continuar →
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
