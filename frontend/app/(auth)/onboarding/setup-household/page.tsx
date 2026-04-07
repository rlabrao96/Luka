"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useLukaStore } from "@/app/lib/store";

export default function SetupHouseholdPage() {
  const router = useRouter();
  const setOnboardingDraft = useLukaStore((s) => s.setOnboardingDraft);
  const draft = useLukaStore((s) => s.onboardingDraft);

  // Check if user came from an invite link — skip this question
  const inviteToken = typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("invite_token") ||
      localStorage.getItem("pending_invite_token")
    : null;

  if (inviteToken) {
    setOnboardingDraft({ type: "individual", partnerEmail: "" });
    router.push("/onboarding/verify-whatsapp");
    return null;
  }

  const [wantsShared, setWantsShared] = useState<boolean | null>(
    draft?.type === "individual" ? false : draft?.type ? true : null
  );

  const nextStep = () => {
    setOnboardingDraft({
      type: wantsShared ? "group" : "individual",
      partnerEmail: "",
    });
    router.push("/onboarding/verify-whatsapp");
  };

  return (
    <Card className="w-full shadow-sm">
      <CardHeader>
        <CardTitle className="text-luka-dark">¿Vas a compartir gastos?</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          variant={wantsShared === true ? "default" : "outline"}
          className="w-full rounded-xl"
          onClick={() => setWantsShared(true)}
        >
          Sí — quiero dividir gastos con otros
        </Button>
        <Button
          variant={wantsShared === false ? "default" : "outline"}
          className="w-full rounded-xl"
          onClick={() => setWantsShared(false)}
        >
          No — solo quiero controlar mis gastos
        </Button>
        {wantsShared !== null && (
          <Button
            className="w-full bg-luka-primary text-white hover:bg-blue-700 rounded-xl"
            onClick={nextStep}
          >
            Continuar →
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
