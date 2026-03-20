import { createClient } from "@/app/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createClient();
  // getSession() reads from local storage — token is kept fresh by Supabase's
  // auto-refresh timer and by middleware's getUser() call on every navigation.
  const { data: { session } } = await supabase.auth.getSession();
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
  bank_name: string | null;
  bank_account_id: string | null;
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

export interface MonthlySpendingPoint {
  month: string;
  personal: number;
  compartido: number;
}

export interface BudgetStatus {
  household_id: string;
  month: string;
  budgeted: number;
  spent: number;
  available: number;
  percent_used: number;
}

// Pace chart
export interface PacePoint {
  day: number;
  cumulative_spent: number;
}

export interface PaceBlock {
  spendable_budget: number;
  daily_points: PacePoint[];
  today_day: number;
  days_in_month: number;
  pace_at_today: number;
  actual_at_today: number;
  delta: number;
  on_track: boolean;
}

// Waterfall budget
export interface PersonalBreakdown {
  household: number;
  personal: number;
}

export interface PersonalBlock {
  ceiling: number;
  ceiling_clamped: boolean;
  spent: number;
  breakdown: PersonalBreakdown;
  available: number;
  percent_used: number | null;
}

export interface HouseholdBlock {
  deposited: number | null;
  spent: number;
  available: number | null;
  percent_used: number | null;
}

export interface PersonalBudgetResponse {
  mode: "single" | "waterfall";
  month: string;
  income: number;
  personal: PersonalBlock;
  pace: PaceBlock;
  household?: HouseholdBlock;
}

// Allocation
export interface AllocationBlock {
  hogar_pct: number;
  ahorro_pct: number;
  personal_pct: number;
  is_default: boolean;
}

export interface AllocationSuggestion {
  hogar_pct: number;
  ahorro_pct: number;
  personal_pct: number;
  label?: string;
}

export interface AllocationResponse {
  month: string;
  allocation: AllocationBlock;
  suggestions: {
    historical: AllocationSuggestion | null;
    recommended: AllocationSuggestion;
  };
}

export interface SetAllocationPayload {
  month: string; // YYYY-MM-DD
  hogar_pct: number;
  ahorro_pct: number;
  personal_pct: number;
}

export interface FintocAccount {
  id: string;       // fintoc_account_id
  name: string;     // e.g. "Cuenta Corriente"
  type: string;     // e.g. "checking_account" | "credit_card"
  number: string;   // e.g. "****1234"
  currency: string;
}

export interface SelectedFintocAccount {
  fintoc_account_id: string;
  label: "personal" | "partner" | "joint";
  currency?: string;
}

export interface ConnectFintocPayload {
  link_token: string;
  household_id: string;
  accounts: SelectedFintocAccount[];
}

export interface ConnectFintocResult {
  created: number;
  accounts: Array<{ id: string; fintoc_account_id: string; account_type: string }>;
}

export interface UpdateBankAccountPayload {
  account_type?: "personal" | "partner" | "joint";
  is_active?: boolean;
}

export interface ImportStatus {
  importing: boolean;
}

export interface BankAccountRow {
  id: string;
  bank_name: string;
  account_type: "personal" | "partner" | "joint";
  account_kind: string | null;
  account_number: string | null;
  cardholder_name: string | null;
  currency: string | null;
  is_active: boolean;
  user_id: string;
  import_status: "pending" | "importing" | "done" | "failed";
  fintoc_account_id: string | null;
  last_synced_at: string | null;
}

// ── API calls ──────────────────────────────────────────────

export const api = {
  getMe: () => apiFetch<UserMe>("/auth/me"),

  getMyTransactions: (since: string) =>
    apiFetch<Transaction[]>(`/transactions/mine?since=${since}`),

  getSharedTransactions: (householdId: string, since: string) =>
    apiFetch<Transaction[]>(`/transactions/shared?household_id=${householdId}&since=${since}`),

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

  acceptInvite: (token: string) =>
    apiFetch<{ household_id: string; accepted_at: string }>(`/invite/${token}`),

  getMonthlySpending: (householdId: string) =>
    apiFetch<MonthlySpendingPoint[]>(`/transactions/monthly-summary?household_id=${householdId}`),

  getFintocAccounts: (linkToken: string) =>
    apiFetch<FintocAccount[]>(
      `/bank-accounts/fintoc/accounts?link_token=${encodeURIComponent(linkToken)}`
    ),

  createHousehold: (name: string, type: "individual" | "couple") =>
    apiFetch<{ id: string; name: string; type: string }>("/households", {
      method: "POST",
      body: JSON.stringify({ name, type }),
    }),

  invitePartner: (householdId: string, email: string) =>
    apiFetch<{ id: string; email: string; household_id: string }>(
      `/households/${householdId}/invite`,
      { method: "POST", body: JSON.stringify({ email }) }
    ),

  connectFintocAccounts: (payload: ConnectFintocPayload) =>
    apiFetch<ConnectFintocResult>("/bank-accounts/fintoc/connect", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getImportStatus: (householdId: string) =>
    apiFetch<ImportStatus>(`/bank-accounts/import-status?household_id=${householdId}`),

  getBankAccounts: (householdId: string) =>
    apiFetch<BankAccountRow[]>(`/bank-accounts?household_id=${householdId}`),

  deleteBankAccount: (accountId: string, householdId: string) =>
    apiFetch<{ ok: boolean }>(`/bank-accounts/${accountId}?household_id=${householdId}`, {
      method: "DELETE",
    }),

  updateBankAccount: (
    accountId: string,
    householdId: string,
    payload: UpdateBankAccountPayload
  ) =>
    apiFetch<{ id: string; account_type: string; is_active: boolean }>(
      `/bank-accounts/${accountId}?household_id=${householdId}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    ),

  updateTransactionCategory: (transactionId: string, category: string | null) =>
    apiFetch<{ ok: boolean }>(`/transactions/${transactionId}/category`, {
      method: "PATCH",
      body: JSON.stringify({ category }),
    }),

  getPersonalBudget: (householdId: string, month?: string) =>
    apiFetch<PersonalBudgetResponse>(
      `/budgets/personal/${householdId}${month ? `?month=${month}` : ""}`
    ),

  getAllocation: (householdId: string, month?: string) =>
    apiFetch<AllocationResponse>(
      `/budgets/allocation/${householdId}${month ? `?month=${month}` : ""}`
    ),

  setAllocation: (householdId: string, payload: SetAllocationPayload) =>
    apiFetch<AllocationBlock>(`/budgets/allocation/${householdId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
