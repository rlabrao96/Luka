"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { SkipForward, Pencil, Check } from "lucide-react";
import { MerchantCard } from "../../../components/MerchantCard";
import { useMerchantReview, useOptimisticReview, useSkipReview } from "@/app/lib/hooks/useMerchantReview";

type SplitType = "personal" | "shared";

export default function ReviewPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const { data: cards = [], isLoading } = useMerchantReview(jobId);
  const { submit } = useOptimisticReview(jobId);
  const skipMutation = useSkipReview(jobId);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editRequested, setEditRequested] = useState(false);
  // Track processed and editing cards for desktop grid
  const [processedIds, setProcessedIds] = useState<Set<string>>(new Set());
  const [editingIds, setEditingIds] = useState<Set<string>>(new Set());
  // Lifted splitType per card so the parent's Approve button can read it
  // (front-state pill toggles live in MerchantCard but mirror up here).
  const [splitTypes, setSplitTypes] = useState<Record<string, SplitType>>({});

  useEffect(() => {
    setEditRequested(false);
  }, [currentIndex]);

  const currentCard = cards[currentIndex];
  const nextCard = cards[currentIndex + 1];
  const total = cards.length;
  const progress = total > 0 ? (currentIndex / total) * 100 : 0;

  const advance = () => {
    if (currentIndex < total - 1) {
      setCurrentIndex((i) => i + 1);
    } else {
      router.push("/transactions");
    }
  };

  // Mobile handlers
  const handleApprove = (
    displayName?: string,
    category?: string,
    splitType?: SplitType
  ) => {
    if (!currentCard) return;
    const effectiveSplit =
      splitType ??
      splitTypes[currentCard.canonical_merchant_id] ??
      (currentCard.is_joint_account ? "shared" : "personal");
    submit(currentCard.canonical_merchant_id, {
      display_name: displayName,
      category,
      split_type: effectiveSplit,
      action: "approve",
    });
    setEditRequested(false);
    advance();
  };

  const handleSkip = () => {
    if (!currentCard) return;
    submit(currentCard.canonical_merchant_id, { action: "skip" });
    setEditRequested(false);
    advance();
  };

  const handleSkipAll = () => {
    skipMutation.mutate(undefined, {
      onSuccess: () => router.push("/transactions"),
    });
  };

  // Desktop grid handlers
  const handleGridApprove = (
    card: typeof cards[0],
    displayName?: string,
    category?: string,
    splitType?: SplitType
  ) => {
    const effectiveSplit =
      splitType ??
      splitTypes[card.canonical_merchant_id] ??
      (card.is_joint_account ? "shared" : "personal");
    submit(card.canonical_merchant_id, {
      display_name: displayName,
      category,
      split_type: effectiveSplit,
      action: "approve",
    });
    setProcessedIds((prev) => new Set(prev).add(card.canonical_merchant_id));
  };

  const handleGridSkip = (card: typeof cards[0]) => {
    submit(card.canonical_merchant_id, { action: "skip" });
    setProcessedIds((prev) => new Set(prev).add(card.canonical_merchant_id));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-4 border-luka-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-lg font-semibold text-luka-dark">No hay comercios para revisar</p>
        <button
          onClick={() => router.push("/transactions")}
          className="mt-4 text-sm text-luka-primary hover:underline"
        >
          Volver a transacciones
        </button>
      </div>
    );
  }

  const remaining = cards.filter((c) => !processedIds.has(c.canonical_merchant_id));
  const processed = cards.filter((c) => processedIds.has(c.canonical_merchant_id));
  const desktopProgress = cards.length > 0 ? (processedIds.size / cards.length) * 100 : 0;

  return (
    <>
      {/* ── Desktop: 3-column card grid ── */}
      <div className="hidden lg:block">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-xl font-bold text-luka-dark">Revisión de comercios</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              {remaining.length > 0
                ? `${remaining.length} de ${cards.length} pendientes`
                : "¡Listo!"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {remaining.length > 0 && (
              <>
                <button
                  onClick={() => {
                    remaining.forEach((c) => handleGridApprove(c));
                  }}
                  className="px-4 py-2 bg-emerald-500 text-white text-sm font-semibold rounded-lg hover:bg-emerald-600 transition-colors flex items-center gap-1.5"
                >
                  <Check size={16} />
                  Aprobar todo
                </button>
                <button
                  onClick={handleSkipAll}
                  className="px-4 py-2 border border-slate-200 text-sm text-slate-500 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  Omitir todo
                </button>
              </>
            )}
          </div>
        </div>

        <div className="bg-slate-100 rounded-full h-1.5 overflow-hidden mb-6">
          <div
            className="bg-luka-primary h-full rounded-full transition-all duration-500 ease-out"
            style={{ width: `${desktopProgress}%` }}
          />
        </div>

        {/* Active cards — 3 per row */}
        {remaining.length > 0 && (
          <div className="grid grid-cols-2 xl:grid-cols-3 gap-5 mb-6">
            {remaining.map((card) => (
              <div key={card.canonical_merchant_id} className="flex flex-col">
                <MerchantCard
                  card={card}
                  onApprove={(dn, cat, st) => {
                    handleGridApprove(card, dn, cat, st);
                    setEditingIds((prev) => { const s = new Set(prev); s.delete(card.canonical_merchant_id); return s; });
                  }}
                  onSplitChange={(st) =>
                    setSplitTypes((prev) => ({ ...prev, [card.canonical_merchant_id]: st }))
                  }
                  editRequested={editingIds.has(card.canonical_merchant_id)}
                />
                {/* Per-card actions */}
                <div className="flex items-center justify-center gap-3 mt-3">
                  <button
                    onClick={() => handleGridSkip(card)}
                    className="w-10 h-10 rounded-full border-2 border-slate-200 flex items-center justify-center text-slate-400 hover:border-slate-300 hover:text-slate-500 transition-colors"
                    title="Omitir"
                  >
                    <SkipForward size={16} />
                  </button>
                  <button
                    onClick={() => setEditingIds((prev) => new Set(prev).add(card.canonical_merchant_id))}
                    className="w-10 h-10 rounded-full border-2 border-red-200 flex items-center justify-center text-red-400 hover:border-red-300 hover:text-red-500 transition-colors"
                    title="Editar"
                  >
                    <Pencil size={16} />
                  </button>
                  <button
                    onClick={() => handleGridApprove(card)}
                    className="w-12 h-12 rounded-full bg-emerald-500 flex items-center justify-center text-white shadow-md shadow-emerald-200 hover:bg-emerald-600 transition-colors"
                    title="Aprobar"
                  >
                    <Check size={20} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Processed cards — faded */}
        {processed.length > 0 && (
          <>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Revisados ({processed.length})
            </p>
            <div className="grid grid-cols-2 xl:grid-cols-3 gap-5 opacity-40">
              {processed.map((card) => (
                <MerchantCard
                  key={card.canonical_merchant_id}
                  card={card}
                  onApprove={() => {}}
                />
              ))}
            </div>
          </>
        )}

        {remaining.length === 0 && (
          <div className="text-center py-12">
            <button
              onClick={() => router.push("/transactions")}
              className="px-6 py-3 bg-luka-primary text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
            >
              Volver a transacciones
            </button>
          </div>
        )}
      </div>

      {/* ── Mobile: Card stack ── */}
      <div className="lg:hidden flex flex-col items-center pt-4">
        <div className="w-full max-w-[380px] mb-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-400">Revisando comercios</span>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400">{currentIndex + 1} / {total}</span>
              <button
                onClick={handleSkipAll}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                Skip All
              </button>
            </div>
          </div>
          <div className="bg-slate-200 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-luka-primary h-full rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="relative w-[340px] min-h-[360px] mb-6">
          {nextCard && (
            <div className="absolute top-2 left-3 right-3 bg-white rounded-2xl shadow-sm h-[340px] opacity-60" />
          )}
          {currentCard && (
            <div className="relative z-10">
              <MerchantCard
                key={currentCard.canonical_merchant_id}
                card={currentCard}
                onApprove={handleApprove}
                onSplitChange={(st) =>
                  setSplitTypes((prev) => ({ ...prev, [currentCard.canonical_merchant_id]: st }))
                }
                editRequested={editRequested}
              />
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={handleSkip}
            className="w-12 h-12 rounded-full border-2 border-slate-200 flex items-center justify-center text-slate-400 hover:border-slate-300 hover:text-slate-500 transition-colors"
            title="Skip"
          >
            <SkipForward size={18} />
          </button>
          <button
            onClick={() => setEditRequested(true)}
            className="w-12 h-12 rounded-full border-2 border-red-200 flex items-center justify-center text-red-400 hover:border-red-300 hover:text-red-500 transition-colors"
            title="Edit"
          >
            <Pencil size={18} />
          </button>
          <button
            onClick={() => handleApprove()}
            className="w-16 h-16 rounded-full bg-green-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-green-200 hover:bg-green-600 transition-colors"
            title="Approve"
          >
            &#10003;
          </button>
        </div>
        <div className="flex items-center gap-4 mt-2 text-[10px] text-slate-400">
          <span className="w-12 text-center">Omitir</span>
          <span className="w-12 text-center">Editar</span>
          <span className="w-16 text-center">Aprobar</span>
        </div>
      </div>
    </>
  );
}
