"use client";
import { useNotifications } from "@/app/lib/hooks/useNotifications";
import { useReviewStatus } from "@/app/lib/hooks/useMerchantReview";

export function ProcessingBanner() {
  const { data: notifications = [] } = useNotifications();

  // Find the most recent merchant_review notification that's still processing
  const processingNotif = notifications.find(
    (n) => n.type === "merchant_review" && n.status === "unread"
  );

  const jobId = processingNotif?.payload?.sync_job_id ?? null;
  const { data: status } = useReviewStatus(jobId);

  if (!status || status.status !== "processing") return null;

  const bankName = processingNotif?.payload?.bank_name ?? "";
  const txCount = processingNotif?.payload?.transaction_count ?? 0;

  return (
    <div className="bg-green-50 border border-green-300 rounded-xl p-4 mb-4">
      <p className="text-sm font-semibold text-green-800">
        Clasificando tus merchants
      </p>
      <p className="text-xs text-green-700 mt-1">
        Estamos organizando {txCount} transacciones de {bankName}. Estaran
        listas para revision en unos momentos.
      </p>
      <div className="mt-3 bg-green-200 rounded-full h-1 overflow-hidden">
        <div className="bg-green-500 h-full rounded-full animate-pulse w-3/5" />
      </div>
    </div>
  );
}
