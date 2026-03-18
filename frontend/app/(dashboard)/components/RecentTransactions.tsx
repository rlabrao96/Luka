import { Transaction } from "@/app/lib/api";
import { cn } from "@/lib/utils";

const SPLIT_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  personal: { label: "Mío",         bg: "bg-blue-50",   text: "text-blue-600"  },
  partner:  { label: "Pareja",      bg: "bg-sky-50",    text: "text-sky-600"   },
  shared:   { label: "Compartido",  bg: "bg-blue-100",  text: "text-blue-700"  },
};

const CATEGORY_EMOJI: Record<string, string> = {
  "Alimentación": "🍔",
  "Transporte":   "🚌",
  "Entretenimiento": "🎬",
  "Salud":        "💊",
  "Hogar":        "🏠",
  "Ropa":         "👕",
  "Tecnología":   "💻",
  "Educación":    "📚",
  "Viajes":       "✈️",
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
    return (
      <div className="py-8 flex flex-col items-center gap-2">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-xl">
          💳
        </div>
        <p className="text-xs text-luka-muted">No hay transacciones aún.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-50">
      {transactions.map((txn) => {
        const split = SPLIT_STYLES[txn.split_type ?? "personal"] ?? SPLIT_STYLES.personal;
        const emoji = CATEGORY_EMOJI[txn.category ?? ""] ?? "💰";

        return (
          <div key={txn.id} className="flex items-center justify-between py-3.5 gap-4 group">
            {/* Icon + info */}
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center text-base shrink-0 group-hover:bg-slate-200 transition-colors">
                {emoji}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-luka-dark truncate">
                  {txn.raw_merchant_name}
                </p>
                <p className="text-xs text-luka-muted mt-0.5">
                  {txn.category ?? "Sin categoría"} · {formatDate(txn.transaction_date)}
                </p>
              </div>
            </div>

            {/* Badge + amount */}
            <div className="flex items-center gap-2.5 shrink-0">
              <span
                className={cn(
                  "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                  split.bg, split.text
                )}
              >
                {split.label}
              </span>
              <span className="text-sm font-bold text-luka-dark tabular-nums">
                {formatCLP(txn.amount)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
