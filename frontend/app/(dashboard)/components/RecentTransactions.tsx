import { Badge } from "@/components/ui/badge";
import { Transaction } from "@/app/lib/api";

const SPLIT_BADGE: Record<string, { label: string; className: string }> = {
  personal: { label: "Mío", className: "bg-green-100 text-green-700" },
  partner:  { label: "Pareja", className: "bg-blue-100 text-blue-700" },
  shared:   { label: "Compartido", className: "bg-yellow-100 text-yellow-700" },
};

function formatCLP(amount: number) {
  return `$${Math.round(amount).toLocaleString("es-CL")}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("es-CL", { day: "2-digit", month: "short" });
}

interface RecentTransactionsProps {
  transactions: Transaction[];
}

export function RecentTransactions({ transactions }: RecentTransactionsProps) {
  if (!transactions.length) {
    return <p className="text-sm text-luka-muted py-4 text-center">No hay transacciones aún.</p>;
  }
  return (
    <div className="divide-y divide-slate-100">
      {transactions.map((txn) => {
        const badge = SPLIT_BADGE[txn.split_type ?? "personal"];
        return (
          <div key={txn.id} className="flex items-center justify-between py-3 gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-luka-dark truncate">{txn.raw_merchant_name}</p>
              <p className="text-xs text-luka-muted">{txn.category ?? "Sin categoría"} · {formatDate(txn.transaction_date)}</p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <Badge className={badge.className}>{badge.label}</Badge>
              <span className="text-sm font-semibold text-luka-dark">{formatCLP(txn.amount)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
