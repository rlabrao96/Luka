"use client";
import type { BankAccountRow } from "@/app/lib/api";

interface BalanceCardProps {
  accounts: BankAccountRow[];
  currency: string;
}

const CHECKING_KINDS = new Set([
  "checking_account", "savings_account", "sight_account", "depository",
]);

function formatBalance(n: number, currency: string): string {
  const isDecimal = currency !== "CLP";
  const displayVal = isDecimal ? n / 100 : n;
  if (currency === "USD")
    return `US$${displayVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(displayVal).toLocaleString("es-CL")}`;
}

export function BalanceCard({ accounts, currency }: BalanceCardProps) {
  const filtered = accounts.filter(
    (a) => a.is_active && a.currency === currency && a.account_kind && CHECKING_KINDS.has(a.account_kind)
  );

  const total = filtered.reduce((s, a) => s + (a.balance_current ?? 0), 0);

  const banks = [...new Set(filtered.map((a) => a.bank_name).filter(Boolean))];
  const subtitle = banks.length > 0 ? banks.join(" + ") : "Sin cuentas";

  return (
    <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl p-4 text-white">
      <p className="text-xs font-medium uppercase tracking-wide opacity-80">
        Saldo disponible
      </p>
      <p className="text-2xl font-bold mt-1 tabular-nums">
        {formatBalance(total, currency)}
      </p>
      <p className="text-xs opacity-70 mt-0.5">{subtitle}</p>
    </div>
  );
}
