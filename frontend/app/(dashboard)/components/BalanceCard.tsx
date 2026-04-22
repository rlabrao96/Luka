"use client";
import { Landmark } from "lucide-react";
import type { BankAccountRow } from "@/app/lib/api";
import { formatStoredAmount, normalizeBalance } from "@/app/lib/currency";

interface BalanceCardProps {
  accounts: BankAccountRow[];
  currency: string;
}

const CHECKING_KINDS = new Set([
  "checking_account", "savings_account", "sight_account", "depository",
]);

export function BalanceCard({ accounts, currency }: BalanceCardProps) {
  const filtered = accounts.filter(
    (a) => a.is_active && a.currency === currency && a.account_kind && CHECKING_KINDS.has(a.account_kind)
  );

  const total = filtered.reduce(
    (s, a) => s + normalizeBalance(a.balance_current ?? 0, currency, a.provider), 0
  );

  const banks = [...new Set(filtered.map((a) => a.bank_name).filter(Boolean))];
  const subtitle = banks.length > 0 ? banks.join(" + ") : "Sin cuentas";

  return (
    <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl p-4 text-white">
      <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center mb-2">
        <Landmark size={16} className="text-white" />
      </div>
      <p className="text-xs font-medium uppercase tracking-wide opacity-80">
        Saldo disponible
      </p>
      <p className="text-2xl font-bold mt-1 tabular-nums">
        {formatStoredAmount(total, currency)}
      </p>
      <p className="text-xs opacity-70 mt-0.5">{subtitle}</p>
    </div>
  );
}
