"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { SkipForward, Pencil } from "lucide-react";
import { MerchantCard } from "../../../components/MerchantCard";
import { useMerchantReview, useOptimisticReview, useSkipReview } from "@/app/lib/hooks/useMerchantReview";

export default function ReviewPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const { data: cards = [], isLoading } = useMerchantReview(jobId);
  const { submit } = useOptimisticReview(jobId);
  const skipMutation = useSkipReview(jobId);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editRequested, setEditRequested] = useState(false);

  // Reset edit state when advancing
  useEffect(() => {
    setEditRequested(false);
  }, [currentIndex]);

  const currentCard = cards[currentIndex];
  const nextCard = cards[currentIndex + 1];
  const total = cards.length;
  const progress = total > 0 ? ((currentIndex) / total) * 100 : 0;

  const advance = () => {
    if (currentIndex < total - 1) {
      setCurrentIndex((i) => i + 1);
    } else {
      router.push("/transactions");
    }
  };

  const handleApprove = (displayName?: string, category?: string) => {
    if (!currentCard) return;
    submit(currentCard.canonical_merchant_id, {
      display_name: displayName,
      category,
      action: "approve",
    });
    advance();
  };

  const handleSkip = () => {
    if (!currentCard) return;
    submit(currentCard.canonical_merchant_id, { action: "skip" });
    advance();
  };

  const handleSkipAll = () => {
    skipMutation.mutate(undefined, {
      onSuccess: () => router.push("/transactions"),
    });
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
        <p className="text-lg font-semibold text-luka-dark">No merchants to review</p>
        <button
          onClick={() => router.push("/transactions")}
          className="mt-4 text-sm text-luka-primary hover:underline"
        >
          Back to transactions
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center pt-4">
      {/* Header */}
      <div className="w-full max-w-[380px] mb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">Reviewing merchants</span>
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

      {/* Card stack */}
      <div className="relative w-[340px] min-h-[360px] mb-6">
        {/* Next card (peek behind) */}
        {nextCard && (
          <div className="absolute top-2 left-3 right-3 bg-white rounded-2xl shadow-sm h-[340px] opacity-60" />
        )}
        {/* Current card */}
        {currentCard && (
          <div className="relative z-10">
            <MerchantCard
              key={currentCard.canonical_merchant_id}
              card={currentCard}
              onApprove={handleApprove}
              onSkip={handleSkip}
              editRequested={editRequested}
            />
          </div>
        )}
      </div>

      {/* Action buttons */}
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
        <span className="w-12 text-center">Skip</span>
        <span className="w-12 text-center">Edit</span>
        <span className="w-16 text-center">Approve</span>
      </div>
    </div>
  );
}
