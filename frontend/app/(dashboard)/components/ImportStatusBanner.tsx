"use client";

import { useImportStatus } from "@/app/lib/hooks/useImportStatus";
import { useLukaStore } from "@/app/lib/store";

export function ImportStatusBanner() {
  const { householdId } = useLukaStore();
  const { importing } = useImportStatus(householdId);

  if (!importing) return null;

  return (
    <div className="bg-blue-50 border-b border-blue-100 px-4 py-2 text-sm text-luka-primary flex items-center gap-2">
      <span className="inline-block h-2 w-2 rounded-full bg-luka-primary animate-pulse" />
      Importando historial de transacciones — esto puede tomar un momento.
    </div>
  );
}
