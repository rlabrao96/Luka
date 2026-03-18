import { createClient } from "@/app/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) return {};
  return { Authorization: `Bearer ${session.access_token}` };
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers: extraHeaders, ...rest } = options ?? {};
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeader, ...extraHeaders },
    ...rest,
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────

export interface UserMe {
  id: string;
  email: string;
  full_name: string;
  email_provider: string;
  whatsapp_verified: boolean;
  household_id: string | null;
}

export interface Transaction {
  id: string;
  raw_merchant_name: string;
  amount: number;
  currency: string;
  transaction_date: string;
  category: string | null;
  source: string;
  status: string;
  split_type: string | null;
}

export interface HouseholdSummaryRow {
  user_id: string;
  full_name: string;
  total_paid: number;
  shared_paid: number;
  personal_paid: number;
}

export interface PartnerStats {
  total_spent: number;
  by_category: Array<{ category: string; amount: number }>;
}

export interface BudgetStatus {
  household_id: string;
  month: string;
  budgeted: number;
  spent: number;
  available: number;
  percent_used: number;
}

// ── API calls ──────────────────────────────────────────────

export const api = {
  getMe: () => apiFetch<UserMe>("/auth/me"),

  getMyTransactions: (limit = 50) =>
    apiFetch<Transaction[]>(`/transactions/mine?limit=${limit}`),

  getSharedTransactions: (householdId: string, limit = 50) =>
    apiFetch<Transaction[]>(`/transactions/shared?household_id=${householdId}&limit=${limit}`),

  getHouseholdSummary: (householdId: string) =>
    apiFetch<HouseholdSummaryRow[]>(`/households/${householdId}/summary`),

  getPartnerStats: (householdId: string) =>
    apiFetch<PartnerStats>(`/households/${householdId}/partner-stats`),

  getBudgetStatus: (householdId: string, month?: string) =>
    apiFetch<BudgetStatus>(`/budgets/monthly/${householdId}${month ? `?month=${month}` : ""}`),

  setBudget: (
    householdId: string,
    body: { bank_account_id: string; month: string; amount: number }
  ) =>
    apiFetch<BudgetStatus>(`/budgets/monthly/${householdId}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
