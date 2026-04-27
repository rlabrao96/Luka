"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { api } from "@/app/lib/api";
import { useQueryClient } from "@tanstack/react-query";

const PLAID_LINK_TOKEN_STORAGE_KEY = "luka.plaid.link_token";

interface PlaidLinkButtonProps {
  onComplete: () => void;
  onError?: (error: string) => void;
}

export function usePlaidConnection({ onComplete, onError }: PlaidLinkButtonProps) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const queryClient = useQueryClient();

  const startPlaidLink = useCallback(async () => {
    setLoading(true);
    try {
      const { link_token } = await api.createPlaidLinkToken();
      // Persist for the OAuth round-trip — banks like Chase/BofA send the user
      // back to /plaid-oauth, where we re-instantiate Plaid Link with this token.
      try {
        window.localStorage.setItem(PLAID_LINK_TOKEN_STORAGE_KEY, link_token);
      } catch {}
      setLinkToken(link_token);
    } catch (e) {
      onError?.("Error al conectar con Plaid");
      setLoading(false);
    }
  }, [onError]);

  const onSuccess = useCallback(
    async (publicToken: string, metadata: any) => {
      try {
        await api.exchangePlaidToken(
          publicToken,
          metadata.institution.institution_id,
          metadata.institution.name
        );
        queryClient.invalidateQueries({ queryKey: ["bank-accounts"] });
        queryClient.invalidateQueries({ queryKey: ["bank-connections"] });
        queryClient.invalidateQueries({ queryKey: ["plaid-items"] });
        onComplete();
      } catch (e) {
        onError?.("Error al vincular cuenta");
      } finally {
        try {
          window.localStorage.removeItem(PLAID_LINK_TOKEN_STORAGE_KEY);
        } catch {}
        setLinkToken(null);
        setLoading(false);
      }
    },
    [onComplete, onError, queryClient]
  );

  const onExit = useCallback(() => {
    try {
      window.localStorage.removeItem(PLAID_LINK_TOKEN_STORAGE_KEY);
    } catch {}
    setLinkToken(null);
    setLoading(false);
  }, []);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
    onExit,
  });

  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  return { startPlaidLink, loading };
}

export { PLAID_LINK_TOKEN_STORAGE_KEY };
