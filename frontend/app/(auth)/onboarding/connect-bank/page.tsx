"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ConnectBankPage() {
  const router = useRouter();

  return (
    <Card className="w-full shadow-sm">
      <CardHeader>
        <CardTitle className="text-luka-dark">Conecta tu banco</CardTitle>
        <CardDescription className="text-luka-muted">
          Conecta tus cuentas bancarias y tarjetas. Importaremos los últimos 3 meses automáticamente.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
          <p className="text-sm text-luka-dark font-medium mb-1">¿Cómo funciona?</p>
          <ul className="text-sm text-luka-muted space-y-1 list-disc list-inside">
            <li>Conecta de forma segura con tu banco</li>
            <li>Elige qué cuentas y tarjetas incluir</li>
            <li>Importamos 3 meses de historial automáticamente</li>
          </ul>
        </div>
        <Button
          onClick={() => {/* Luka Connect modal — Task 14 */}}
          className="w-full bg-luka-primary text-white hover:bg-blue-700 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        >
          Conectar banco
        </Button>
        <button
          onClick={() => router.push("/")}
          className="w-full text-sm text-luka-muted hover:text-luka-dark text-center"
        >
          Saltar por ahora
        </button>
      </CardContent>
    </Card>
  );
}
