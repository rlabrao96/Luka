"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { RecentTransactions } from "../components/RecentTransactions";
import { useMyTransactions, useSharedTransactions } from "@/app/lib/hooks/useTransactions";
import { Transaction } from "@/app/lib/api";

export default function TransactionsPage() {
  const [search, setSearch] = useState("");
  const { data: myTxns = [], isLoading: loadingMine } = useMyTransactions(200);
  const { data: sharedTxns = [], isLoading: loadingShared } = useSharedTransactions(200);

  const filter = (txns: Transaction[]) =>
    search
      ? txns.filter(
          (t) =>
            t.raw_merchant_name.toLowerCase().includes(search.toLowerCase()) ||
            (t.category ?? "").toLowerCase().includes(search.toLowerCase())
        )
      : txns;

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-luka-dark">Transacciones</h2>
      <Input
        placeholder="Buscar por comercio o categoría..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />
      <Tabs defaultValue="mine">
        <TabsList>
          <TabsTrigger value="mine">Mías ({myTxns.length})</TabsTrigger>
          <TabsTrigger value="shared">Compartidas ({sharedTxns.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="mine">
          <Card className="bg-white">
            <CardContent className="pt-4">
              {loadingMine ? (
                <p className="text-sm text-luka-muted">Cargando...</p>
              ) : (
                <RecentTransactions transactions={filter(myTxns)} />
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="shared">
          <Card className="bg-white">
            <CardContent className="pt-4">
              {loadingShared ? (
                <p className="text-sm text-luka-muted">Cargando...</p>
              ) : (
                <RecentTransactions transactions={filter(sharedTxns)} />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
