"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

const BANKS = ["Santander", "Banco de Chile", "BCI", "Scotiabank", "Itaú", "BICE", "Otro"];

export default function ConnectBankPage() {
  const router = useRouter();
  const [bank, setBank] = useState("");
  const [accountType, setAccountType] = useState<"personal" | "joint" | null>(null);

  const save = async () => {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/bank-accounts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bank_name: bank.toLowerCase(), account_type: accountType }),
    });
    router.push("/dashboard");
  };

  return (
    <Card>
      <CardHeader><CardTitle>Agrega tu banco</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <select className="w-full border rounded p-2 text-sm" value={bank} onChange={e => setBank(e.target.value)}>
          <option value="">Selecciona tu banco</option>
          {BANKS.map(b => <option key={b} value={b}>{b}</option>)}
        </select>
        <Button variant={accountType === "personal" ? "default" : "outline"}
          className="w-full" onClick={() => setAccountType("personal")}>
          Cuenta personal
        </Button>
        <Button variant={accountType === "joint" ? "default" : "outline"}
          className="w-full" onClick={() => setAccountType("joint")}>
          Cuenta conjunta (con tarjetas adicionales)
        </Button>
        {bank && accountType && (
          <Button className="w-full bg-luka-primary" onClick={save}>Ir al Dashboard →</Button>
        )}
      </CardContent>
    </Card>
  );
}
