"use client";
import { useId, useMemo, useState } from "react";
import { ArrowLeftRight, ChevronDown, Undo2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, type BankAccountRow, type Transaction } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { formatStoredAmount } from "@/app/lib/currency";
import { toTitleCase } from "@/app/lib/strings";
import { cn } from "@/lib/utils";
import { TransactionCard } from "./TransactionCard";
import { DirectionIcon } from "./DirectionIcon";

const WALLET_MERCHANT_RE = /\b(venmo|paypal|cash ?app)\b/i;

/* ─── Public types + grouping helper ──────────────────────────────── */

export type TransactionOrPair =
  | { kind: "single"; txn: Transaction }
  | {
      kind: "pair";
      pairId: string;
      pairType: "transfer" | "refund";
      legs: Transaction[];
    };

/**
 * Walk `txns` in input order and fold rows that share a `transfer_pair_id`
 * or `refund_pair_id` into a single `pair` entry. Pairs emit at the
 * position of their FIRST leg; subsequent legs are swallowed. All other
 * rows emit as `single`.
 *
 * This is a visual grouping only — server totals already exclude paired
 * rows via `exclude_from_totals` (backend Task 2.10), so do NOT reuse
 * this helper to filter category charts or budget aggregations.
 */
export function groupPairs(txns: Transaction[]): TransactionOrPair[] {
  const out: TransactionOrPair[] = [];
  const pairIndex = new Map<string, number>(); // pairId → index in `out`

  for (const txn of txns) {
    const transferId = txn.transfer_pair_id;
    const refundId = txn.refund_pair_id;
    const pairId = transferId ?? refundId ?? null;

    if (!pairId) {
      out.push({ kind: "single", txn });
      continue;
    }

    const existing = pairIndex.get(pairId);
    if (existing !== undefined) {
      const entry = out[existing];
      if (entry.kind === "pair") entry.legs.push(txn);
      continue;
    }

    const pairType: "transfer" | "refund" = transferId ? "transfer" : "refund";
    pairIndex.set(pairId, out.length);
    out.push({ kind: "pair", pairId, pairType, legs: [txn] });
  }

  // Collapse pairs whose twin leg was filtered out of the visible list back
  // to a single-transaction render. Otherwise the user sees a misleading
  // "Transferencia · 1 transacción" card. If the user filtered to one side
  // of a pair, showing that side as a normal row is the right UX.
  return out.map((entry) =>
    entry.kind === "pair" && entry.legs.length < 2
      ? { kind: "single", txn: entry.legs[0] }
      : entry,
  );
}

/* ─── PairedTransactionCard ──────────────────────────────────────── */

interface PairedTransactionCardProps {
  pairId: string;
  pairType: "transfer" | "refund";
  legs: Transaction[];
}

function looksLikeCCPayment(name: string): boolean {
  const n = name.toLowerCase();
  return (
    n.includes("pago tarjeta") ||
    n.includes("pago tc") ||
    n.includes("credit card payment") ||
    n.includes("tarjeta de credito") ||
    n.includes("tarjeta de crédito")
  );
}

export function PairedTransactionCard({
  // `pairId` is kept in the interface for clarity at the call site and so
  // React tooling can use it as a stable identity when needed, even though
  // the component itself doesn't read it (React key is set by the parent).
  pairId: _pairId,
  pairType,
  legs,
}: PairedTransactionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  const householdId = useLukaStore((s) => s.householdId);

  // Reuse TanStack's existing cache key from transactions/page.tsx so we
  // piggyback on any already-fetched accounts list rather than refetch.
  const { data: accounts = [] } = useQuery<BankAccountRow[]>({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 60 * 1000,
  });

  const accountNameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const a of accounts) {
      m.set(a.id, a.account_name ?? a.bank_name);
    }
    return m;
  }, [accounts]);

  // Detect wallet pairs: one leg has a wallet-token merchant (the bank-side
  // funding/cashout row, e.g. "Venmo"), the other has the counterparty name
  // (the wallet-side row, e.g. "Nicolas Celasco"). These are rendered as the
  // canonical expense/income, not as a generic inter-account transfer.
  const walletBankLeg =
    pairType === "transfer" && legs.length === 2
      ? legs.find((l) => WALLET_MERCHANT_RE.test(l.raw_merchant_name))
      : undefined;
  const walletCanonicalLeg =
    walletBankLeg
      ? legs.find((l) => l.id !== walletBankLeg.id && !WALLET_MERCHANT_RE.test(l.raw_merchant_name))
      : undefined;
  const isWalletPair = !!(walletBankLeg && walletCanonicalLeg);

  // Pick the leg used for the summary amount/title. Wallet pairs use the
  // canonical leg (real counterparty); other pairs use the negative leg.
  const summaryLeg =
    isWalletPair
      ? walletCanonicalLeg!
      : (legs.find((l) => Number(l.amount) < 0) ?? legs[0]);
  const currency = summaryLeg.currency ?? "CLP";
  const summaryAmount = Number(summaryLeg.amount) || 0;
  const summaryIsOutflow = summaryAmount < 0;
  const absAmount = Math.abs(summaryAmount);
  const formattedAbs = formatStoredAmount(-absAmount, currency).replace(/^\(|\)$/g, "");
  // For wallet pairs we show a signed amount (parens for expense). Others
  // stay neutral/slate as before.
  const formattedSigned = formatStoredAmount(summaryAmount, currency);

  let title: string;
  let subtitle: string;
  if (isWalletPair) {
    title = toTitleCase(walletCanonicalLeg!.raw_merchant_name);
    const walletName = walletCanonicalLeg!.bank_account_id
      ? accountNameById.get(walletCanonicalLeg!.bank_account_id)
      : undefined;
    const bankName = walletBankLeg!.bank_account_id
      ? accountNameById.get(walletBankLeg!.bank_account_id)
      : undefined;
    if (walletName && bankName) {
      subtitle = summaryIsOutflow
        ? `${toTitleCase(walletName)} · pagado con ${toTitleCase(bankName)}`
        : `${toTitleCase(walletName)} · depositado en ${toTitleCase(bankName)}`;
    } else {
      subtitle = "Venmo";
    }
  } else if (pairType === "transfer") {
    const isCCPayment = legs.some((l) => looksLikeCCPayment(l.raw_merchant_name));
    title = isCCPayment ? "Pago tarjeta" : "Transferencia";
    // Transfer legs live on two different accounts; the negative leg is
    // "from", the positive leg is "to".
    const fromLeg = legs.find((l) => Number(l.amount) < 0);
    const toLeg = legs.find((l) => Number(l.amount) > 0);
    const fromName = fromLeg?.bank_account_id
      ? accountNameById.get(fromLeg.bank_account_id)
      : undefined;
    const toName = toLeg?.bank_account_id
      ? accountNameById.get(toLeg.bank_account_id)
      : undefined;
    subtitle = fromName && toName ? `${toTitleCase(fromName)} → ${toTitleCase(toName)}` : "Entre cuentas";
  } else {
    const merchant = toTitleCase(summaryLeg.raw_merchant_name);
    title = `${merchant} · reembolsado`;
    // Both legs share the same bank account for a refund.
    const accountName = summaryLeg.bank_account_id
      ? accountNameById.get(summaryLeg.bank_account_id)
      : undefined;
    subtitle = accountName ? `en ${toTitleCase(accountName)}` : "Reembolso aplicado";
  }

  const legCount = legs.length;
  const ariaLabel =
    pairType === "refund"
      ? `${title} ${formattedAbs}, neto cero`
      : isWalletPair
        ? `${title} ${formattedSigned}, ${legCount} transacciones`
        : `${title} ${formattedAbs}, ${legCount} transacciones`;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls={panelId}
        aria-label={ariaLabel}
        className="w-full text-left p-3 sm:p-3.5 flex items-center gap-2 sm:gap-3 hover:bg-slate-50/50 transition-colors"
      >
        {/* Icon */}
        {isWalletPair ? (
          <DirectionIcon direction={summaryIsOutflow ? "outflow" : "inflow"} />
        ) : (
          <div
            className={cn(
              "hidden sm:flex w-[38px] h-[38px] rounded-[10px] items-center justify-center shrink-0",
              pairType === "transfer" ? "bg-blue-50 text-blue-500" : "bg-slate-100 text-slate-500"
            )}
            aria-hidden="true"
          >
            {pairType === "transfer" ? (
              <ArrowLeftRight size={16} strokeWidth={2.5} />
            ) : (
              <Undo2 size={16} strokeWidth={2.5} />
            )}
          </div>
        )}

        <div className="flex-1 min-w-0">
          {/* Line 1: title + amount */}
          <div className="flex justify-between items-baseline gap-2">
            <p className="text-[13px] sm:text-sm font-semibold text-luka-dark truncate">
              {title}
            </p>
            {isWalletPair ? (
              <span
                className={cn(
                  "text-[13px] sm:text-[15px] font-bold tabular-nums shrink-0",
                  summaryIsOutflow ? "text-luka-dark" : "text-emerald-600",
                )}
              >
                {formattedSigned}
              </span>
            ) : pairType === "transfer" ? (
              <span className="text-[13px] sm:text-[15px] font-bold tabular-nums shrink-0 text-slate-500">
                {formattedAbs}
              </span>
            ) : (
              <span className="flex items-baseline gap-1.5 shrink-0">
                <span className="text-[12px] sm:text-[14px] font-semibold tabular-nums line-through text-slate-400">
                  {formattedAbs}
                </span>
                <span className="text-[10px] sm:text-[11px] font-bold tabular-nums text-emerald-600">
                  $0
                </span>
              </span>
            )}
          </div>

          {/* Line 2: subtitle + chevron */}
          <div className="flex justify-between items-center mt-1">
            <p className="text-[10px] sm:text-[11px] text-slate-400 truncate">
              {subtitle}
              <span className="ml-1.5 text-slate-300">· {legCount} transacciones</span>
            </p>
            <ChevronDown
              size={14}
              className={cn(
                "shrink-0 text-slate-400 transition-transform duration-200",
                expanded ? "rotate-180" : "",
              )}
              aria-hidden="true"
            />
          </div>
        </div>
      </button>

      {expanded && (
        <div id={panelId} className="border-t border-slate-100 bg-slate-50/60 p-2 sm:p-3 space-y-1.5">
          {legs.map((leg) => (
            <div key={leg.id} className="pl-2 sm:pl-4 border-l-2 border-slate-200">
              <TransactionCard txn={leg} compact />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
