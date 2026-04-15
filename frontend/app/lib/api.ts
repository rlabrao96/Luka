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
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail ?? `API error ${res.status}`;
    throw new Error(detail);
  }
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
}

export interface CategoryBudgetResponse {
  household_id: string;
  month: string;
  budgets: CategoryBudgetItem[];
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
}

export interface ReviewStatus {
  job_id: string;
  status: "processing" | "ready" | "completed" | "skipped" | "failed";
  total_merchants: number | null;
  reviewed_count: number;
}

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

  getCategoryBudgets: (householdId: string, month?: string) =>
    apiFetch<CategoryBudgetResponse>(
      `/budgets/categories/${householdId}${month ? `?month=${month}` : ""}`
    ),

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
    apiFetch<{ household_id: string; accepted_at: string }>(`/invite/${token}`),

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

  updateTransactionCategory: (transactionId: string, category: string | null) =>
    apiFetch<{ ok: boolean }>(`/transactions/${transactionId}/category`, {
      method: "PATCH",
      body: JSON.stringify({ category }),
    }),

  updateTransactionSplitType: (transactionId: string, splitType: string) =>
    apiFetch<{ ok: boolean }>(`/transactions/${transactionId}/split-type`, {
      method: "PATCH",
      body: JSON.stringify({ split_type: splitType }),
    }),

  getPersonalBudget: (householdId: string, month?: string, currency?: string) => {
    const parts: string[] = [];
    if (month) parts.push(`month=${month}`);
    if (currency) parts.push(`currency=${currency}`);
    const qs = parts.length ? `?${parts.join("&")}` : "";
    return apiFetch<PersonalBudgetResponse>(`/budgets/personal/${householdId}${qs}`);
  },

  getAllocation: (householdId: string, month?: string, currency?: string) => {
    const parts: string[] = [];
    if (month) parts.push(`month=${month}`);
    if (currency) parts.push(`currency=${currency}`);
    const qs = parts.length ? `?${parts.join("&")}` : "";
    return apiFetch<AllocationResponse>(`/budgets/allocation/${householdId}${qs}`);
  },

  setAllocation: (householdId: string, payload: SetAllocationPayload) =>
    apiFetch<AllocationBlock>(`/budgets/allocation/${householdId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

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
  approveMerchant: (jobId: string, canonicalId: string, data: { display_name?: string; category?: string; action: string }) =>
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

  // --- Cuotas (Chunk E) ---
  createCuota: (payload: {
    merchant_name: string;
    total_amount: number;
    currency: "CLP" | "USD";
    installments_total: number;
    first_cuota_date: string;
    split_type?: "personal" | "shared";
    origin_transaction_id?: string | null;
  }) =>
    apiFetch<{ id: string }>("/cuotas", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listCuotas: (scope: "personal" | "household" = "personal") =>
    apiFetch<{ cuotas: unknown[] }>(`/cuotas?scope=${scope}`),

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
};

// ── Budget V2 (redesign) types ────────────────────────────────

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
