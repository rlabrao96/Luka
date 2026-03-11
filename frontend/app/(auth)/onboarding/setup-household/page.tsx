"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

export default function SetupHouseholdPage() {
  const router = useRouter();
  const [type, setType] = useState<"individual" | "couple" | null>(null);
  const [partnerEmail, setPartnerEmail] = useState("");

  const create = async () => {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/households`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Mi Hogar", type }),
    });
    const household = await res.json();

    if (type === "couple" && partnerEmail && household.id) {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/households/${household.id}/invite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: partnerEmail }),
      });
    }

    router.push("/onboarding/connect-bank");
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
