"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

import { api } from "@/app/lib/api";

export default function SetupHouseholdPage() {
  const router = useRouter();
  const [type, setType] = useState<"individual" | "couple" | null>(null);
  const [partnerEmail, setPartnerEmail] = useState("");

  const create = async () => {
    try {
      const household = await api.createHousehold("Mi Hogar", type!);

      if (type === "couple" && partnerEmail && household.id) {
        await api.invitePartner(household.id, partnerEmail);
      }

      router.push("/onboarding/connect-bank");
    } catch (e) {
      console.error("Failed to setup household:", e);
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle>¿Cómo usarás Luka?</CardTitle></CardHeader>
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
          <Button className="w-full bg-luka-primary" onClick={create}>Continuar →</Button>
        )}
      </CardContent>
    </Card>
  );
}
