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

export class ApiError extends Error {
  status: number;
  code: string | null;
  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers: extraHeaders, ...rest } = options ?? {};
  const authHeader = await getAuthHeader();
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeader, ...extraHeaders },
    ...rest,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    // Backend may send either a plain string or a {code, message} object.
    if (detail && typeof detail === "object" && "message" in detail) {
      throw new ApiError(res.status, String(detail.message), detail.code ?? null);
    }
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : `API error ${res.status}`,
    );
  }
  // 204 No Content (e.g. DELETE /transactions/{id}) has an empty body —
  // res.json() would throw "Unexpected end of JSON input".
  if (res.status === 204) return undefined as T;
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────

export interface UserMe {
  id: string;
  email: string;
  full_name: string;
  email_provider: string;
  whatsapp_verified: boolean;
  phone_whatsapp: string | null;
  preferred_currency: string;
  household_id: string | null;
  // Contribution fields for the caller's active household membership.
  // Null when the user has no active membership.
  contribution_mode: "full" | "fixed" | "reimbursement" | null;
  // Quantized decimal string from the backend (e.g. "800000.00"), not a number.
  // Pydantic v2 serializes Decimal as string, and the auth router explicitly
  // normalizes to the Numeric(14, 2) scale via a field_serializer. Read sites
  // must convert with Number(...) before doing arithmetic or comparisons.
  fixed_contribution_amount: string | null;
  fixed_contribution_currency: string | null;
  feature_trips_enabled: boolean;
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
  account_kind: string | null;
  transaction_type: string | null;
  source_type: string | null;
  display_name: string | null;
  // Pair ids for CC-transfer and refund grouping (Task 4.5).
  // Paired rows are excluded from totals on the server; the UI collapses
  // them into a single "Pago tarjeta" / "reembolsado" card.
  transfer_pair_id: string | null;
  refund_pair_id: string | null;
  // User-declared reimbursement grouping (migration 044). N+1 rows sharing
  // a UUID net to zero in spending totals; the UI groups them as one card.
  reimbursement_group_id: string | null;
  // Lifecycle timestamps (Task 4.6). ISO8601 strings from the backend.
  // `created_at` drives the PendingBlock age badge (backlog indicator);
  // `orphaned_at` records when a row was dismissed / aged out.
  created_at: string | null;
  orphaned_at: string | null;
}

export interface PendingTransactions {
  awaiting_reconciliation: Transaction[];
  needs_classification: Transaction[];
  unmatched_email: Transaction[];
}

export interface HouseholdSummaryRow {
  user_id: string;
  full_name: string;
  email: string;
  total_paid: number;
  shared_paid: number;
  personal_paid: number;
}

export interface MemberStats {
  user_id: string;
  full_name: string;
  total_spent: number;
}

export interface MemberTotal {
  user_id: string;
  full_name: string;
  amount: number;
  pct: number;
}

export interface CategoryBreakdownRow {
  category: string;
  member_totals: MemberTotal[];
  total: number;
  pct_of_overall: number;
}

export interface SettlementTransfer {
  from_user_id: string;
  from_user_name: string;
  to_user_id: string;
  to_user_name: string;
  amount: number;
}

export interface SettlementResponse {
  settlement_enabled: boolean;
  transfers: SettlementTransfer[];
  split_ratio: number[];
  month: string;
}

export interface SplitRatioResponse {
  split_ratio: number[];
}

export interface HouseholdMember {
  member_id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: "owner" | "member";
  joined_at: string;
}

export interface PendingInvite {
  id: string;
  token: string;
  invited_email: string | null;
  expires_at: string;
  created_at: string;
}

export interface HouseholdMembersResponse {
  members: HouseholdMember[];
  pending_invites: PendingInvite[];
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

export interface CategoryBudgetItem {
  category: string;
  amount: number;
  currency?: string;
}

export interface CategoryBudgetResponse {
  household_id: string;
  month: string;
  budgets: CategoryBudgetItem[];
}

export interface UpdateBankAccountPayload {
  account_type?: "personal" | "partner" | "joint";
  is_active?: boolean;
}

export interface BankAccountRow {
  id: string;
  bank_name: string;
  account_type: "personal" | "partner" | "joint";
  account_kind: string | null;
  account_name: string | null;
  account_number: string | null;
  cardholder_name: string | null;
  currency: string | null;
  is_active: boolean;
  user_id: string;
  last_synced_at: string | null;
  balance_current: number | null;
  balance_limit: number | null;
  country: string | null;
  provider: string | null;
  plaid_item_id: string | null;
  error_code: string | null;
}

export interface RecentCharge {
  date: string;
  amount: number;
}

export interface RecurringExpense {
  merchant_name: string;
  category: string | null;
  average_amount: number;
  last_amount: number;
  previous_amount: number | null;
  last_charge_date: string;
  next_charge_day: number;
  frequency: string;
  trend: "stable" | "increased" | "decreased";
  trend_pct: number | null;
  months_seen: number;
  split_type: string;
  currency: string;
  status: string;
  recent_charges: RecentCharge[];
}

export interface SubscriptionsSummary {
  total_recurring: number;
  monthly_total: number;
  pct_of_total: number;
  count: number;
}

export interface SubscriptionsResponse {
  items: RecurringExpense[];
  summary_by_currency: Record<string, SubscriptionsSummary>;
  computed_at: string | null;
}

export interface SubscriptionOverrideBody {
  merchant_key: string;
  status?: string | null;
  category?: string | null;
  next_charge_day?: number | null;
  split_type?: "personal" | "shared" | null;
}

// --- Luka Connect ---

export interface ConnectBankPayload {
  bank_code: string;
  rut: string;
  password: string;
}

export interface SyncStatus {
  bank_code: string;
  last_sync_at: string | null;
  last_sync_status: string | null;
  current_job_id: string | null;
  next_sync_at: string | null;
}

export interface BankConnection {
  bank_code: string;
  bank_name?: string;
  last_sync_at: string | null;
  last_sync_status: string | null;
  next_sync_at: string | null;
  country?: string;
}

export interface PlaidItem {
  id: string;
  institution_name: string;
  institution_id: string;
  last_sync_at: string | null;
  last_sync_status: string | null;
  error_code: string | null;
  country: string;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  status: string;
  payload: {
    bank_name?: string;
    transaction_count?: number;
    sync_job_id?: string;
    merchant_count?: number;
  } | null;
  created_at: string;
  read_at: string | null;
}

export interface CreditSuggestionItem {
  id: string;
  status: string;
  title: string;
  credit_txn_id: string;
  counterpart_txn_id: string;
  amount: number;
  currency: string;
  merchant_credit_name: string;
  merchant_counterpart_name: string;
  credit_date: string;
  counterpart_date: string;
  bank_account_id: string | null;
  created_at: string;
}

export interface ReviewTransactionInfo {
  raw_name: string;
  date: string | null;
  amount: number;
  currency: string;
}

export interface ReviewCard {
  canonical_merchant_id: string;
  display_name: string;
  default_category: string | null;
  llm_suggested_categories: string[];
  transactions: ReviewTransactionInfo[];
  transaction_count: number;
  total_amount: number;
  currency: string;
  is_verified: boolean;
  is_joint_account: boolean;
}

export interface ReviewStatus {
  job_id: string;
  status: "processing" | "ready" | "completed" | "skipped" | "failed";
  total_merchants: number | null;
  reviewed_count: number;
}

export interface UserCurrency {
  currency_code: string;
  is_primary: boolean;
  sort_order: number;
}

// Match candidate row from GET /transactions/{id}/match-candidates.
// Mirrors backend schemas.MatchCandidate: amount is a Decimal string on the
// wire, consumers Number(...) before arithmetic.
export interface MatchCandidate {
  id: string;
  bank_account_id: string | null;
  bank_account_name: string | null;
  transaction_date: string;
  amount: number;
  currency: string;
  raw_merchant_name: string;
  category: string | null;
  status: string | null;
  // Populated for intent="reimbursement" — used by ReimbursementLinkDialog
  // to render the source-type chip and bank label without a second query.
  source_type?: string | null;
  bank_name?: string | null;
}

export type BulkActionKind = "dismiss" | "delete";

// ── API calls ──────────────────────────────────────────────

export const api = {
  getMe: () => apiFetch<UserMe>("/auth/me"),

  getMyTransactions: (since: string) =>
    apiFetch<Transaction[]>(`/transactions/mine?since=${since}`),

  getSharedTransactions: (householdId: string, since: string) =>
    apiFetch<Transaction[]>(`/transactions/shared?household_id=${householdId}&since=${since}`),

  getPendingTransactions: () =>
    apiFetch<PendingTransactions>("/transactions/pending"),

  deleteTransaction: (id: string) =>
    apiFetch<void>(`/transactions/${id}`, { method: "DELETE" }),

  // Phase 3 consolidation endpoints --------------------------------------

  getMatchCandidates: (
    pendingId: string,
    opts: {
      windowDays?: number;
      intent?: "consolidate" | "transfer" | "reimbursement";
      q?: string;
    } = {},
  ) => {
    const windowDays = opts.windowDays ?? 7;
    const intent = opts.intent ?? "consolidate";
    const params = new URLSearchParams({
      window_days: String(windowDays),
      intent,
    });
    if (opts.q && opts.q.trim()) params.set("q", opts.q.trim());
    return apiFetch<MatchCandidate[]>(
      `/transactions/${pendingId}/match-candidates?${params.toString()}`,
    );
  },

  linkTransaction: (pendingId: string, bankTransactionId: string) =>
    apiFetch<Transaction>(`/transactions/${pendingId}/link`, {
      method: "POST",
      body: JSON.stringify({ bank_transaction_id: bankTransactionId }),
    }),

  linkTransfer: (transactionId: string, counterpartId: string) =>
    apiFetch<{ transfer_pair_id: string; transaction_ids: string[] }>(
      `/transactions/${transactionId}/link-transfer`,
      {
        method: "POST",
        body: JSON.stringify({ counterpart_id: counterpartId }),
      },
    ),

  linkReimbursement: (transactionId: string, counterpartIds: string[]) =>
    apiFetch<{ reimbursement_group_id: string; transaction_ids: string[] }>(
      `/transactions/${transactionId}/link-reimbursement`,
      {
        method: "POST",
        body: JSON.stringify({ counterpart_ids: counterpartIds }),
      },
    ),

  unlinkReimbursement: (groupId: string) =>
    apiFetch<{ unlinked: number }>(
      `/transactions/reimbursement-group/${groupId}`,
      { method: "DELETE" },
    ),

  // --- Credit suggestions (auto-detected reimbursements) ---
  getCreditSuggestions: () =>
    apiFetch<CreditSuggestionItem[]>("/transactions/credit-suggestions"),

  confirmCreditSuggestion: (notificationId: string) =>
    apiFetch<{ reimbursement_group_id: string; transaction_ids: string[] }>(
      `/transactions/credit-suggestions/${notificationId}/confirm`,
      { method: "POST" },
    ),

  dismissCreditSuggestion: (notificationId: string) =>
    apiFetch<{ ok: boolean }>(
      `/transactions/credit-suggestions/${notificationId}/dismiss`,
      { method: "POST" },
    ),

  updateTransactionDate: (transactionId: string, transactionDate: string) =>
    apiFetch<{ ok: boolean }>(`/transactions/${transactionId}/transaction-date`, {
      method: "PATCH",
      body: JSON.stringify({ transaction_date: transactionDate }),
    }),

  dismissTransaction: (id: string) =>
    apiFetch<void>(`/transactions/${id}/dismiss`, { method: "POST" }),

  bulkAction: (transactionIds: string[], action: BulkActionKind) =>
    apiFetch<{ processed: number }>("/transactions/bulk-action", {
      method: "POST",
      body: JSON.stringify({ transaction_ids: transactionIds, action }),
    }),

  updateCategory: (id: string, category: string) =>
    apiFetch<{ ok: boolean }>(`/transactions/${id}/category`, {
      method: "PATCH",
      body: JSON.stringify({ category }),
    }),

  getHouseholdSummary: (householdId: string, currency?: string) => {
    const params = currency ? `?currency=${currency}` : "";
    return apiFetch<HouseholdSummaryRow[]>(`/households/${householdId}/summary${params}`);
  },

  getMemberStats: (householdId: string) =>
    apiFetch<MemberStats[]>(`/households/${householdId}/member-stats`),

  getCategoryBreakdown: (householdId: string, month?: string, currency?: string) => {
    const parts: string[] = [];
    if (month) parts.push(`month=${month}`);
    if (currency) parts.push(`currency=${currency}`);
    const qs = parts.length ? `?${parts.join("&")}` : "";
    return apiFetch<CategoryBreakdownRow[]>(`/households/${householdId}/category-breakdown${qs}`);
  },
  getSettlement: (householdId: string, month?: string, currency?: string) => {
    const parts: string[] = [];
    if (month) parts.push(`month=${month}`);
    if (currency) parts.push(`currency=${currency}`);
    const qs = parts.length ? `?${parts.join("&")}` : "";
    return apiFetch<SettlementResponse>(`/households/${householdId}/settlement${qs}`);
  },
  getSplitRatio: (householdId: string) =>
    apiFetch<SplitRatioResponse>(`/households/${householdId}/split-ratio`),
  updateSplitRatio: (householdId: string, ratio: number[]) =>
    apiFetch<SplitRatioResponse>(`/households/${householdId}/split-ratio`, {
      method: "PATCH",
      body: JSON.stringify({ ratio }),
    }),

  getBudgetStatus: (householdId: string, month?: string, currency?: string) => {
    const parts: string[] = [];
    if (month) parts.push(`month=${month}`);
    if (currency) parts.push(`currency=${currency}`);
    const qs = parts.length ? `?${parts.join("&")}` : "";
    return apiFetch<BudgetStatus>(`/budgets/monthly/${householdId}${qs}`);
  },

  getCategoryBudgets: (householdId: string, month?: string, currency?: string) => {
    const qs = new URLSearchParams();
    if (month) qs.set("month", month);
    if (currency) qs.set("currency", currency);
    const q = qs.toString();
    return apiFetch<CategoryBudgetResponse>(
      `/budgets/categories/${householdId}${q ? `?${q}` : ""}`
    );
  },

  setCategoryBudgets: (householdId: string, body: { month: string; budgets: CategoryBudgetItem[] }) =>
    apiFetch<CategoryBudgetResponse>(`/budgets/categories/${householdId}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  setBudget: (
    householdId: string,
    body: { bank_account_id: string; month: string; amount: number }
  ) =>
    apiFetch<BudgetStatus>(`/budgets/monthly/${householdId}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  acceptInvite: (token: string) =>
    apiFetch<{ household_id: string; accepted_at: string }>(`/invite/${token}`, {
      method: "POST",
    }),

  getMonthlySpending: (householdId: string, currency?: string) => {
    const parts: string[] = [`household_id=${householdId}`];
    if (currency) parts.push(`currency=${currency}`);
    return apiFetch<MonthlySpendingPoint[]>(
      `/transactions/monthly-summary?${parts.join("&")}`
    );
  },

  createHousehold: (name: string, type: "individual" | "group") =>
    apiFetch<{ id: string; name: string; type: string }>("/households", {
      method: "POST",
      body: JSON.stringify({ name, type }),
    }),

  inviteMember: (householdId: string, email: string) =>
    apiFetch<{ token: string; expires_at: string }>(
      `/households/${householdId}/invite`,
      { method: "POST", body: JSON.stringify({ email }) }
    ),

  getHouseholdMembers: (householdId: string) =>
    apiFetch<HouseholdMembersResponse>(`/households/${householdId}/members`),

  createAndInvite: (email: string) =>
    apiFetch<{ household_id: string; token: string; expires_at: string }>(
      "/households/create-and-invite",
      { method: "POST", body: JSON.stringify({ email }) }
    ),

  updateSettlementEnabled: (householdId: string, enabled: boolean) =>
    apiFetch<{ settlement_enabled: boolean }>(
      `/households/${householdId}/settlement-enabled`,
      { method: "PATCH", body: JSON.stringify({ enabled }) }
    ),

  updateMemberRole: (householdId: string, memberId: string, role: string) =>
    apiFetch<{ ok: boolean }>(
      `/households/${householdId}/members/${memberId}/role`,
      { method: "PATCH", body: JSON.stringify({ role }) }
    ),

  removeMember: (householdId: string, memberId: string) =>
    apiFetch<{ ok: boolean; new_household_id: string }>(
      `/households/${householdId}/members/${memberId}`,
      { method: "DELETE" }
    ),

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

  syncBalances: (householdId: string) =>
    apiFetch<{ updated: number }>(`/bank-accounts/sync-balances?household_id=${householdId}`, {
      method: "POST",
    }),

  updateTransactionCategory: (
    transactionId: string,
    category: string | null,
    options?: { apply_to_all_matching?: boolean },
  ) =>
    apiFetch<{ ok: boolean; updated_count: number }>(
      `/transactions/${transactionId}/category`,
      {
        method: "PATCH",
        body: JSON.stringify({
          category,
          apply_to_all_matching: options?.apply_to_all_matching ?? false,
        }),
      },
    ),

  getCategoryMatchingCount: (transactionId: string, category: string | null) => {
    const params = new URLSearchParams();
    if (category != null) params.set("category", category);
    const qs = params.toString();
    return apiFetch<{
      count: number;
      raw_merchant_name: string;
      merchant_id: string | null;
      current_category: string | null;
    }>(
      `/transactions/${transactionId}/category/matching-count${qs ? `?${qs}` : ""}`,
    );
  },

  updateTransactionSplitType: (transactionId: string, splitType: string) =>
    apiFetch<{ ok: boolean }>(`/transactions/${transactionId}/split-type`, {
      method: "PATCH",
      body: JSON.stringify({ split_type: splitType }),
    }),

  updateMerchantName: (
    transactionId: string,
    payload: {
      raw_merchant_name?: string | null;
      merchant_id?: string | null;
      apply_to_all_matching?: boolean;
    },
  ) =>
    apiFetch<{ ok: boolean; updated_count: number }>(
      `/transactions/${transactionId}/merchant-name`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    ),

  getMerchantNameMatchingCount: (transactionId: string) =>
    apiFetch<{
      count: number;
      raw_merchant_name: string;
      merchant_id: string | null;
    }>(`/transactions/${transactionId}/merchant-name/matching-count`),

  // --- Luka Connect ---
  connectBank: (payload: ConnectBankPayload) =>
    apiFetch("/bank-connect/connect", { method: "POST", body: JSON.stringify(payload) }),

  disconnectBank: (bankCode: string) =>
    apiFetch(`/bank-connect/disconnect?bank_code=${bankCode}`, { method: "DELETE" }),

  getSyncStatus: (bankCode: string): Promise<SyncStatus> =>
    apiFetch(`/bank-connect/sync-status?bank_code=${bankCode}`),

  manualSync: (bankCode: string, daysBack: number = 4) =>
    apiFetch(`/bank-connect/sync?bank_code=${bankCode}&days_back=${daysBack}`, { method: "POST" }),

  getBankConnections: (): Promise<BankConnection[]> =>
    apiFetch("/bank-connect/connections"),

  // --- Plaid (US banks) ---
  createPlaidLinkToken: () =>
    apiFetch<{ link_token: string }>("/plaid/create-link-token", { method: "POST" }),

  exchangePlaidToken: (publicToken: string, institutionId: string, institutionName: string) =>
    apiFetch<{ plaid_item_id: string }>("/plaid/exchange-token", {
      method: "POST",
      body: JSON.stringify({
        public_token: publicToken,
        institution_id: institutionId,
        institution_name: institutionName,
      }),
    }),

  disconnectPlaid: (plaidItemId: string) =>
    apiFetch(`/plaid/disconnect?plaid_item_id=${plaidItemId}`, { method: "DELETE" }),

  syncPlaid: (plaidItemId: string) =>
    apiFetch(`/plaid/sync?plaid_item_id=${plaidItemId}`, { method: "POST" }),

  getPlaidItems: (): Promise<PlaidItem[]> =>
    apiFetch("/plaid/items"),

  // --- Profile ---
  async updateProfile(payload: { full_name?: string; phone_whatsapp?: string; preferred_currency?: string }) {
    return apiFetch<UserMe>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  // --- Notifications ---
  async getNotificationPreferences() {
    return apiFetch<{ whatsapp_enabled: boolean }>("/notifications/preferences");
  },

  async updateNotificationPreferences(whatsapp_enabled: boolean) {
    return apiFetch<{ whatsapp_enabled: boolean }>("/notifications/preferences", {
      method: "PATCH",
      body: JSON.stringify({ whatsapp_enabled }),
    });
  },

  // --- Categories ---
  async getCategoryPreferences() {
    return apiFetch<{
      categories: Array<{
        category: string;
        sort_order: number;
        category_type: "expense" | "income";
        is_custom: boolean;
      }>;
    }>("/categories/preferences");
  },

  async reorderCategoryPreferences(
    categories: Array<{ category: string; sort_order: number }>
  ) {
    return apiFetch<{
      categories: Array<{
        category: string;
        sort_order: number;
        category_type: "expense" | "income";
        is_custom: boolean;
      }>;
    }>("/categories/preferences", {
      method: "PUT",
      body: JSON.stringify({ categories }),
    });
  },

  async addCategory(category: string, category_type: "expense" | "income") {
    return apiFetch<{
      category: string;
      sort_order: number;
      category_type: "expense" | "income";
      is_custom: boolean;
    }>("/categories/preferences", {
      method: "POST",
      body: JSON.stringify({ category, category_type }),
    });
  },

  async getCategoryUsage(category: string) {
    return apiFetch<{ count: number }>(
      `/categories/preferences/${encodeURIComponent(category)}/usage`
    );
  },

  async deleteCategory(category: string, reclassify_to: string | null) {
    return apiFetch<{ ok: boolean }>(
      `/categories/preferences/${encodeURIComponent(category)}/delete`,
      {
        method: "POST",
        body: JSON.stringify({ reclassify_to }),
      }
    );
  },

  // --- Household partner categories (read-only with respect to partner data) ---
  async getHouseholdPartnerCategories() {
    return apiFetch<{
      categories: Array<{
        category: string;
        category_type: "expense" | "income";
        member_ids: string[];
        count: number;
      }>;
    }>("/settings/household-categories");
  },

  async adoptHouseholdCategory(
    category: string,
    category_type: "expense" | "income"
  ) {
    return apiFetch<{
      already_present: boolean;
      category?: string;
      sort_order?: number;
      category_type?: "expense" | "income";
      is_custom?: boolean;
    }>("/settings/household-categories/adopt", {
      method: "POST",
      body: JSON.stringify({ category, category_type }),
    });
  },

  // --- WhatsApp PIN ---
  sendWhatsAppPin: (phone: string) =>
    apiFetch<{ status: string }>("/auth/send-whatsapp-pin", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),

  verifyWhatsAppPin: (phone: string, pin: string) =>
    apiFetch<{ status: string }>("/auth/verify-whatsapp-pin", {
      method: "POST",
      body: JSON.stringify({ phone, pin }),
    }),

  getSubscriptions: (monthsBack?: number) =>
    apiFetch<SubscriptionsResponse>(`/subscriptions/detected${monthsBack ? `?months_back=${monthsBack}` : ""}`),

  refreshSubscriptions: () =>
    apiFetch<SubscriptionsResponse>("/subscriptions/refresh", { method: "POST" }),

  upsertSubscriptionOverride: (body: SubscriptionOverrideBody) =>
    apiFetch<{ ok: boolean }>("/subscriptions/override", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  // --- Notifications ---
  getNotifications: () => apiFetch<NotificationItem[]>("/notifications"),
  getUnreadCount: () => apiFetch<{ count: number }>("/notifications/unread-count"),
  updateNotification: (id: string, status: string) =>
    apiFetch<NotificationItem>(`/notifications/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  deleteNotification: (id: string) =>
    apiFetch<{ ok: boolean }>(`/notifications/${id}`, { method: "DELETE" }),

  // --- Merchant Review ---
  getReviewCards: (jobId: string) => apiFetch<ReviewCard[]>(`/merchant-review/${jobId}`),
  getReviewStatus: (jobId: string) => apiFetch<ReviewStatus>(`/merchant-review/${jobId}/status`),
  approveMerchant: (jobId: string, canonicalId: string, data: { display_name?: string; category?: string; split_type?: "personal" | "shared"; action: string }) =>
    apiFetch<{ ok: boolean }>(`/merchant-review/${jobId}/merchants/${canonicalId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  skipReview: (jobId: string) =>
    apiFetch<{ ok: boolean }>(`/merchant-review/${jobId}/skip`, { method: "POST" }),
  dismissReview: (jobId: string) =>
    apiFetch<{ ok: boolean }>(`/merchant-review/${jobId}`, { method: "DELETE" }),

  // --- Budget settings (savings target + payday + personal allocation) ---
  getBudgetSettings: () =>
    apiFetch<{
      savings_target_amount: number | null;
      savings_target_currency: string | null;
      payday_day_of_month: number | null;
      personal_allocation_amount: number | null;
      personal_allocation_currency: string | null;
    }>("/settings/budget"),

  updateBudgetSettings: (payload: {
    savings_target_amount: number | null;
    savings_target_currency: string | null;
    payday_day_of_month: number | null;
    personal_allocation_amount?: number | null;
    personal_allocation_currency?: string | null;
  }) =>
    apiFetch<{
      savings_target_amount: number | null;
      savings_target_currency: string | null;
      payday_day_of_month: number | null;
      personal_allocation_amount: number | null;
      personal_allocation_currency: string | null;
    }>("/settings/budget", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // --- Currencies ---
  getCurrencies(): Promise<UserCurrency[]> {
    return apiFetch<UserCurrency[]>("/currencies");
  },

  addCurrency(currency_code: string): Promise<UserCurrency> {
    return apiFetch<UserCurrency>("/currencies", {
      method: "POST",
      body: JSON.stringify({ currency_code }),
    });
  },

  deleteCurrency(currency_code: string): Promise<void> {
    return apiFetch<void>(`/currencies/${currency_code}`, { method: "DELETE" });
  },

  // --- Delete Account ---
  async deleteAccount() {
    const authHeader = await getAuthHeader();
    const res = await fetch(`${API_URL}/auth/me`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", ...authHeader, "X-Confirm-Delete": "ELIMINAR" },
    });
    if (!res.ok) throw new Error(`API error ${res.status}: /auth/me`);
  },

  // --- Contribution mode (Chunk D) ---
  updateContribution: (payload: {
    mode: "full" | "fixed" | "reimbursement";
    fixed_amount: number | null;
    fixed_currency: string | null;
  }) =>
    apiFetch<{
      mode: string;
      fixed_amount: number | null;
      fixed_currency: string | null;
    }>("/households/settings/contribution", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // --- Cuotas ---
  createCuota: (
    householdId: string,
    payload: {
      merchant_name: string;
      total_amount: number;
      currency: string;
      installments_total: number;
      first_cuota_date: string;
      split_type?: "personal" | "shared";
      origin_transaction_id?: string | null;
    },
  ) =>
    apiFetch<{ id: string }>(`/cuotas?household_id=${householdId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listCuotas: (
    scope: "personal" | "household" = "personal",
    householdId?: string,
  ) => {
    const qs =
      scope === "household" && householdId
        ? `?scope=household&household_id=${householdId}`
        : `?scope=${scope}`;
    return apiFetch<{ cuotas: unknown[] }>(`/cuotas${qs}`);
  },

  cancelCuota: (cuotaId: string) =>
    apiFetch<{ ok: boolean }>(`/cuotas/${cuotaId}`, { method: "DELETE" }),

  // ── Budget V2 (redesign) ──────────────────────────────────────
  getBudgetV2: (
    householdId: string,
    params: { month?: string; currency?: string; view?: "personal" | "household" } = {}
  ) => {
    const qs = new URLSearchParams();
    if (params.month) qs.set("month", params.month);
    if (params.currency) qs.set("currency", params.currency);
    if (params.view) qs.set("view", params.view);
    const q = qs.toString();
    return apiFetch<BudgetV2Response>(`/budgets/v2/${householdId}${q ? `?${q}` : ""}`);
  },

  getBudgetNodeDrilldown: (
    householdId: string,
    params: {
      node_id: string;
      view: "personal" | "household";
      month?: string;
      currency?: string;
      limit?: number;
    }
  ) => {
    const qs = new URLSearchParams();
    qs.set("node_id", params.node_id);
    qs.set("view", params.view);
    if (params.month) qs.set("month", params.month);
    if (params.currency) qs.set("currency", params.currency);
    if (params.limit) qs.set("limit", String(params.limit));
    return apiFetch<BudgetV2DrilldownBlock>(
      `/budgets/v2/${householdId}/drilldown?${qs.toString()}`
    );
  },
};

// ── Budget V2 (redesign) types ────────────────────────────────

export interface BudgetV2DrilldownItem {
  id: string;
  date: string; // ISO date (YYYY-MM-DD)
  merchant: string;
  amount: number;
  category: string | null;
  bank_name: string | null;
  split_type: string | null;
}

export interface BudgetV2DrilldownBlock {
  node_id: string;
  label: string;
  kind: "transactions" | "empty";
  empty_reason: string | null;
  items: BudgetV2DrilldownItem[];
}

export interface BudgetV2SankeyNode {
  id: string;
  label: string;
  value: number;
  risk?: boolean;
  // Budget v3 rank-based fields (null/absent on legacy responses)
  level?: number | null;
  kind?: "source" | "hub" | "allocation" | "spent" | null;
  member_id?: string | null;
}

export interface BudgetV2SankeyLink {
  source: string;
  target: string;
  value: number;
}

export interface BudgetV2SankeyBlock {
  nodes: BudgetV2SankeyNode[];
  links: BudgetV2SankeyLink[];
}

export interface BudgetV2SpendableBlock {
  amount: number;
  spent: number;
  remaining: number;
  pct_used: number;
}

export interface BudgetV2RiskCategory {
  name: string;
  spent: number;
  cap: number;
  historical_mean: number;
  historical_std: number;
  p_overshoot: number;
  projected_final: number;
  alert: boolean;
}

export interface BudgetV2RunwayBlock {
  days_remaining: number;
  days_to_payday: number;
  daily_burn_14d: number;
  alert: boolean;
}

export interface BudgetV2CuotasBlock {
  this_month: number;
  future_total: number;
  active_count: number;
}

export interface BudgetV2SavingsTargetBlock {
  target: number;
  progress: number;
  pct_complete: number;
}

export interface BudgetV2Response {
  view: "personal" | "household";
  month: string;
  currency: string;
  currencies_available: string[];
  sankey: BudgetV2SankeyBlock;
  spendable: BudgetV2SpendableBlock;
  risk_categories: BudgetV2RiskCategory[];
  runway: BudgetV2RunwayBlock;
  cuotas: BudgetV2CuotasBlock;
  savings_target: BudgetV2SavingsTargetBlock;
}

// =========================================================================
// Trips (Viajes) — backend behind users.feature_trips_enabled flag.
// Endpoints return 403 when the flag is off; the nav-gate keeps users out
// of trip pages, but mid-session flips surface naturally via TanStack Query
// error states.
//
// Decimal fields cross the wire as strings (Pydantic field_serializer) — read
// sites must Number(...) before doing arithmetic / comparisons.
// =========================================================================

export interface TripAttendee {
  id: string;
  user_id: string | null;
  display_name: string;
  left_at: string | null;
  created_at: string;
}

export interface TripSplit {
  attendee_id: string;
  share_amount: string;
  share_type: "equal" | "custom_amount" | "custom_percent";
}

export interface TripExpense {
  id: string;
  trip_id: string;
  payer_attendee_id: string;
  description: string;
  amount: string;
  currency: string;
  expense_date: string;
  transaction_id: string | null;
  fx_rate_to_base: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  splits: TripSplit[];
}

export interface TripSettlement {
  id: string;
  trip_id: string;
  from_attendee_id: string;
  to_attendee_id: string;
  amount: string;
  currency: string;
  fx_rate_to_base: string | null;
  settled_at: string;
  transaction_id: string | null;
  write_off: boolean;
  created_at: string;
}

export interface TripBalance {
  attendee_id: string;
  attendee_display_name: string | null;
  net_in_base: string;
}

export interface TripSettleSuggestion {
  from_attendee_id: string;
  to_attendee_id: string;
  amount: string;
  currency: string;
}

export interface Trip {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  base_currency: string;
  status: "active" | "archived";
  created_at: string;
  your_net_balance: string;
}

export interface TripDetail extends Trip {
  attendees: TripAttendee[];
  expenses: TripExpense[];
  settlements: TripSettlement[];
  balances: TripBalance[];
  settle_suggestions: TripSettleSuggestion[];
}

export interface TripList {
  active: Trip[];
  upcoming: Trip[];
  past: Trip[];
}

export interface CreateAttendeeInput {
  email?: string | null;
  phone?: string | null;
  display_name?: string | null;
}

export interface CreateTripInput {
  name: string;
  start_date: string;
  end_date: string;
  base_currency: string;
  attendees?: CreateAttendeeInput[];
}

export interface UpdateTripInput {
  name?: string;
  start_date?: string;
  end_date?: string;
  base_currency?: string;
}

export interface SplitInput {
  attendee_id: string;
  share_amount?: string | null;
  share_percent?: string | null;
  share_type?: "equal" | "custom_amount" | "custom_percent";
}

export interface CreateExpenseInput {
  payer_attendee_id: string;
  description: string;
  amount: string;
  currency: string;
  expense_date: string;
  transaction_id?: string | null;
  splits: SplitInput[];
}

export interface UpdateExpenseInput {
  payer_attendee_id?: string;
  description?: string;
  amount?: string;
  currency?: string;
  expense_date?: string;
  transaction_id?: string | null;
  splits?: SplitInput[];
}

export interface CreateSettlementInput {
  from_attendee_id: string;
  to_attendee_id: string;
  amount: string;
  currency: string;
  transaction_id?: string | null;
}

export interface InviteLink {
  token: string;
  url: string;
  expires_at: string;
}

export interface TripPreview {
  name: string;
  start_date: string;
  end_date: string;
  attendee_count: number;
  base_currency: string;
}

export interface SuggestedTransaction {
  transaction_id: string;
  merchant: string | null;
  amount: string;
  currency: string;
  transaction_date: string;
  category: string | null;
}

export interface ConfirmSettlementSuggestionInput {
  trip_id: string;
  transaction_id: string;
  from_attendee_id: string;
  to_attendee_id: string;
  amount: string;
  currency: string;
}

export const tripsApi = {
  list: () => apiFetch<TripList>("/trips"),
  get: (id: string) => apiFetch<TripDetail>(`/trips/${id}`),
  create: (body: CreateTripInput) =>
    apiFetch<Trip>("/trips", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: UpdateTripInput) =>
    apiFetch<Trip>(`/trips/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  archive: (id: string) =>
    apiFetch<void>(`/trips/${id}`, { method: "DELETE" }),

  addAttendee: (tripId: string, body: CreateAttendeeInput) =>
    apiFetch<TripAttendee>(`/trips/${tripId}/attendees`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  removeAttendee: (tripId: string, attendeeId: string) =>
    apiFetch<void>(`/trips/${tripId}/attendees/${attendeeId}`, {
      method: "DELETE",
    }),
  forceRemoveAttendee: (tripId: string, attendeeId: string) =>
    apiFetch<void>(`/trips/${tripId}/attendees/${attendeeId}/force-remove`, {
      method: "POST",
    }),

  createExpense: (tripId: string, body: CreateExpenseInput) =>
    apiFetch<TripExpense>(`/trips/${tripId}/expenses`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateExpense: (
    tripId: string,
    expenseId: string,
    version: number,
    body: UpdateExpenseInput,
  ) =>
    apiFetch<TripExpense>(`/trips/${tripId}/expenses/${expenseId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      headers: { "If-Match": String(version) },
    }),
  deleteExpense: (tripId: string, expenseId: string) =>
    apiFetch<void>(`/trips/${tripId}/expenses/${expenseId}`, {
      method: "DELETE",
    }),

  createSettlement: (tripId: string, body: CreateSettlementInput) =>
    apiFetch<TripSettlement>(`/trips/${tripId}/settlements`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  generateInviteLink: (tripId: string) =>
    apiFetch<InviteLink>(`/trips/${tripId}/invite-link`, { method: "POST" }),
  revokeInviteLink: (tripId: string) =>
    apiFetch<void>(`/trips/${tripId}/invite-link`, { method: "DELETE" }),
  joinViaToken: (token: string) =>
    apiFetch<TripDetail>(`/trips/join/${token}`, { method: "POST" }),
  previewByToken: (token: string) =>
    apiFetch<TripPreview>(`/trips/preview/${token}`),

  suggestedTransactions: (tripId: string) =>
    apiFetch<SuggestedTransaction[]>(
      `/trips/${tripId}/suggested-transactions`,
    ),
  dismissSuggestion: (tripId: string, transactionId: string) =>
    apiFetch<void>(
      `/trips/${tripId}/suggested-transactions/${transactionId}/dismiss`,
      { method: "POST" },
    ),
  undismissSuggestion: (tripId: string, transactionId: string) =>
    apiFetch<void>(
      `/trips/${tripId}/suggested-transactions/${transactionId}/dismiss`,
      { method: "DELETE" },
    ),

  confirmSettlementSuggestion: (body: ConfirmSettlementSuggestionInput) =>
    apiFetch<TripSettlement>(`/trips/settlement-suggestions/confirm`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  dismissSettlementSuggestion: (transaction_id: string) =>
    apiFetch<void>(`/trips/settlement-suggestions/dismiss`, {
      method: "POST",
      body: JSON.stringify({ transaction_id }),
    }),
};
