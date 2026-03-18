"use client";

import { useEffect, useState } from "react";
import { api } from "@/app/lib/api";

const POLL_INTERVAL_MS = 5000;

export function useImportStatus(householdId: string | null) {
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!householdId) return;

    let active = true;
    let timeoutId: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const { importing: isImporting } = await api.getImportStatus(householdId!);
        if (!active) return;
        setImporting(isImporting);
        if (isImporting) {
          timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch {
        if (active) {
          timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    }

    poll();
    return () => {
      active = false;
      clearTimeout(timeoutId);
    };
  }, [householdId]);

  return { importing };
}
