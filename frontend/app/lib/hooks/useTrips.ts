"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  tripsApi,
  type CreateTripInput,
  type UpdateTripInput,
  type CreateAttendeeInput,
  type CreateExpenseInput,
  type UpdateExpenseInput,
  type CreateSettlementInput,
  type ConfirmSettlementSuggestionInput,
  type SuggestedTransaction,
  type Trip,
  type TripAttendee,
  type TripDetail,
  type TripExpense,
  type TripList,
  type TripSettlement,
  type TripSplit,
} from "@/app/lib/api";

const TRIPS_KEY = ["trips"] as const;
const tripKey = (id: string) => ["trips", id] as const;
const suggestedKey = (id: string) => ["trips", id, "suggested-transactions"] as const;

// ---------------------------------------------------------------------------
// Optimistic-update helpers
// ---------------------------------------------------------------------------

function tempId(prefix: string): string {
  // crypto.randomUUID isn't available in older browsers; fall back to a
  // timestamp+random string — these IDs only ever live in the client cache
  // and are replaced by the server's real ID on success.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID()}`;
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function classifyTripBucket(
  startDate: string,
  endDate: string,
): "active" | "upcoming" | "past" {
  const today = new Date();
  const todayKey = today.toISOString().slice(0, 10);
  if (todayKey < startDate) return "upcoming";
  if (todayKey > endDate) return "past";
  return "active";
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useTrips() {
  return useQuery({
    queryKey: TRIPS_KEY,
    queryFn: () => tripsApi.list(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrip(id: string | null) {
  return useQuery({
    queryKey: id ? tripKey(id) : ["trips", "null"],
    queryFn: () =>
      id ? tripsApi.get(id) : Promise.reject(new Error("no id")),
    enabled: !!id,
  });
}

// ---------------------------------------------------------------------------
// Trip-level mutations
// ---------------------------------------------------------------------------

export function useCreateTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTripInput) => tripsApi.create(body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: TRIPS_KEY });
      const prev = qc.getQueryData<TripList>(TRIPS_KEY);
      if (prev) {
        const placeholder: Trip = {
          id: tempId("trip"),
          name: body.name,
          start_date: body.start_date,
          end_date: body.end_date,
          base_currency: body.base_currency.toUpperCase(),
          status: "active",
          creator_user_id: "", // filled by server
          created_at: new Date().toISOString(),
          your_net_balance: "0",
        };
        const bucket = classifyTripBucket(body.start_date, body.end_date);
        qc.setQueryData<TripList>(TRIPS_KEY, {
          ...prev,
          [bucket]: [placeholder, ...prev[bucket]],
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(TRIPS_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

export function useUpdateTrip(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateTripInput) => tripsApi.update(id, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: tripKey(id) });
      const prev = qc.getQueryData<TripDetail>(tripKey(id));
      if (prev) {
        qc.setQueryData<TripDetail>(tripKey(id), {
          ...prev,
          ...(body.name !== undefined ? { name: body.name } : {}),
          ...(body.start_date !== undefined ? { start_date: body.start_date } : {}),
          ...(body.end_date !== undefined ? { end_date: body.end_date } : {}),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(tripKey(id), ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: TRIPS_KEY });
      qc.invalidateQueries({ queryKey: tripKey(id) });
    },
  });
}

export function useArchiveTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tripsApi.archive(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: TRIPS_KEY });
      const prev = qc.getQueryData<TripList>(TRIPS_KEY);
      if (prev) {
        const filter = (xs: Trip[]) => xs.filter((t) => t.id !== id);
        qc.setQueryData<TripList>(TRIPS_KEY, {
          active: filter(prev.active),
          upcoming: filter(prev.upcoming),
          past: filter(prev.past),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(TRIPS_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

// ---------------------------------------------------------------------------
// Attendee mutations
// ---------------------------------------------------------------------------

export function useAddAttendee(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateAttendeeInput) =>
      tripsApi.addAttendee(tripId, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: tripKey(tripId) });
      const prev = qc.getQueryData<TripDetail>(tripKey(tripId));
      if (prev) {
        const fallbackName =
          body.display_name ??
          (body.email ? body.email.split("@")[0] : null) ??
          body.phone ??
          "Invitado";
        const placeholder: TripAttendee = {
          id: tempId("att"),
          user_id: null,
          display_name: fallbackName,
          left_at: null,
          created_at: new Date().toISOString(),
        };
        qc.setQueryData<TripDetail>(tripKey(tripId), {
          ...prev,
          attendees: [...prev.attendees, placeholder],
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(tripKey(tripId), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

export function useRemoveAttendee(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (attendeeId: string) =>
      tripsApi.removeAttendee(tripId, attendeeId),
    onMutate: async (attendeeId) => {
      await qc.cancelQueries({ queryKey: tripKey(tripId) });
      const prev = qc.getQueryData<TripDetail>(tripKey(tripId));
      if (prev) {
        const now = new Date().toISOString();
        qc.setQueryData<TripDetail>(tripKey(tripId), {
          ...prev,
          attendees: prev.attendees.map((a) =>
            a.id === attendeeId && a.left_at === null
              ? { ...a, left_at: now }
              : a,
          ),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(tripKey(tripId), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

export function useForceRemoveAttendee(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (attendeeId: string) =>
      tripsApi.forceRemoveAttendee(tripId, attendeeId),
    onMutate: async (attendeeId) => {
      await qc.cancelQueries({ queryKey: tripKey(tripId) });
      const prev = qc.getQueryData<TripDetail>(tripKey(tripId));
      if (prev) {
        const now = new Date().toISOString();
        qc.setQueryData<TripDetail>(tripKey(tripId), {
          ...prev,
          attendees: prev.attendees.map((a) =>
            a.id === attendeeId ? { ...a, left_at: now } : a,
          ),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(tripKey(tripId), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

// ---------------------------------------------------------------------------
// Expense mutations
// ---------------------------------------------------------------------------

function buildOptimisticSplits(
  body: CreateExpenseInput,
): TripSplit[] {
  // Server normalizes share amounts; for a clean optimistic UI we floor
  // to cents and let the payer absorb the remainder (matches backend
  // _normalize_splits).
  const totalCents = Math.round(Number(body.amount) * 100);
  const n = body.splits.length;
  if (n === 0) return [];
  if (body.splits[0].share_type === "custom_amount") {
    return body.splits.map((s) => ({
      attendee_id: s.attendee_id,
      share_amount: s.share_amount ?? "0",
      share_type: "custom_amount",
    }));
  }
  if (body.splits[0].share_type === "custom_percent") {
    const out: TripSplit[] = body.splits.map((s) => {
      const pct = Number(s.share_percent ?? 0);
      const cents = Math.floor((totalCents * pct) / 100);
      return {
        attendee_id: s.attendee_id,
        share_amount: (cents / 100).toFixed(2),
        share_type: "custom_percent",
      };
    });
    const sumCents = out.reduce(
      (acc, s) => acc + Math.round(Number(s.share_amount) * 100),
      0,
    );
    const residual = totalCents - sumCents;
    if (residual !== 0) {
      const idx = out.findIndex((s) => s.attendee_id === body.payer_attendee_id);
      const target = idx >= 0 ? idx : 0;
      out[target] = {
        ...out[target],
        share_amount: (
          (Math.round(Number(out[target].share_amount) * 100) + residual) /
          100
        ).toFixed(2),
      };
    }
    return out;
  }
  // equal
  const each = Math.floor(totalCents / n);
  const out: TripSplit[] = body.splits.map((s) => ({
    attendee_id: s.attendee_id,
    share_amount: (each / 100).toFixed(2),
    share_type: "equal",
  }));
  const residual = totalCents - each * n;
  if (residual !== 0) {
    const idx = out.findIndex((s) => s.attendee_id === body.payer_attendee_id);
    const target = idx >= 0 ? idx : 0;
    out[target] = {
      ...out[target],
      share_amount: ((each + residual) / 100).toFixed(2),
    };
  }
  return out;
}

export function useCreateExpense(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateExpenseInput) =>
      tripsApi.createExpense(tripId, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: tripKey(tripId) });
      await qc.cancelQueries({ queryKey: suggestedKey(tripId) });
      const prevTrip = qc.getQueryData<TripDetail>(tripKey(tripId));
      const prevSuggested = qc.getQueryData<SuggestedTransaction[]>(
        suggestedKey(tripId),
      );
      if (prevTrip) {
        const placeholder: TripExpense = {
          id: tempId("exp"),
          trip_id: tripId,
          payer_attendee_id: body.payer_attendee_id,
          description: body.description,
          amount: body.amount,
          currency: body.currency.toUpperCase(),
          expense_date: body.expense_date,
          transaction_id: body.transaction_id ?? null,
          fx_rate_to_base: null,
          version: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          splits: buildOptimisticSplits(body),
        };
        qc.setQueryData<TripDetail>(tripKey(tripId), {
          ...prevTrip,
          expenses: [placeholder, ...prevTrip.expenses],
        });
      }
      // If linked to a transaction, drop it from the suggestions list.
      if (body.transaction_id && prevSuggested) {
        qc.setQueryData<SuggestedTransaction[]>(
          suggestedKey(tripId),
          prevSuggested.filter((s) => s.transaction_id !== body.transaction_id),
        );
      }
      return { prevTrip, prevSuggested };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prevTrip) qc.setQueryData(tripKey(tripId), ctx.prevTrip);
      if (ctx?.prevSuggested)
        qc.setQueryData(suggestedKey(tripId), ctx.prevSuggested);
    },
    onSettled: () => {
      // Prefix invalidation: also refreshes the trips LIST (your_net_balance
      // on the index) — tripKey alone left it stale for up to 5 minutes.
      qc.invalidateQueries({ queryKey: TRIPS_KEY });
    },
  });
}

export function useUpdateExpense(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      expenseId,
      version,
      body,
    }: {
      expenseId: string;
      version: number;
      body: UpdateExpenseInput;
    }) => tripsApi.updateExpense(tripId, expenseId, version, body),
    onMutate: async ({ expenseId, body }) => {
      await qc.cancelQueries({ queryKey: tripKey(tripId) });
      const prev = qc.getQueryData<TripDetail>(tripKey(tripId));
      if (prev) {
        qc.setQueryData<TripDetail>(tripKey(tripId), {
          ...prev,
          expenses: prev.expenses.map((e) =>
            e.id === expenseId
              ? {
                  ...e,
                  ...(body.description !== undefined
                    ? { description: body.description }
                    : {}),
                  ...(body.amount !== undefined ? { amount: body.amount } : {}),
                  ...(body.currency !== undefined
                    ? { currency: body.currency.toUpperCase() }
                    : {}),
                  ...(body.expense_date !== undefined
                    ? { expense_date: body.expense_date }
                    : {}),
                  ...(body.payer_attendee_id !== undefined
                    ? { payer_attendee_id: body.payer_attendee_id }
                    : {}),
                  ...(body.transaction_id !== undefined
                    ? { transaction_id: body.transaction_id }
                    : {}),
                  ...(body.splits
                    ? {
                        splits: buildOptimisticSplits({
                          ...body,
                          payer_attendee_id:
                            body.payer_attendee_id ?? e.payer_attendee_id,
                          description: body.description ?? e.description,
                          amount: body.amount ?? e.amount,
                          currency: body.currency ?? e.currency,
                          expense_date: body.expense_date ?? e.expense_date,
                          splits: body.splits,
                        }),
                      }
                    : {}),
                  updated_at: new Date().toISOString(),
                }
              : e,
          ),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(tripKey(tripId), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

export function useDeleteExpense(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (expenseId: string) =>
      tripsApi.deleteExpense(tripId, expenseId),
    onMutate: async (expenseId) => {
      await qc.cancelQueries({ queryKey: tripKey(tripId) });
      const prev = qc.getQueryData<TripDetail>(tripKey(tripId));
      if (prev) {
        qc.setQueryData<TripDetail>(tripKey(tripId), {
          ...prev,
          expenses: prev.expenses.filter((e) => e.id !== expenseId),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(tripKey(tripId), ctx.prev);
    },
    onSettled: () => {
      // Prefix invalidation: also refreshes the trips LIST (your_net_balance
      // on the index) — tripKey alone left it stale for up to 5 minutes.
      qc.invalidateQueries({ queryKey: TRIPS_KEY });
    },
  });
}

// ---------------------------------------------------------------------------
// Settlement mutations
// ---------------------------------------------------------------------------

export function useCreateSettlement(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateSettlementInput) =>
      tripsApi.createSettlement(tripId, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: tripKey(tripId) });
      const prev = qc.getQueryData<TripDetail>(tripKey(tripId));
      if (prev) {
        const placeholder: TripSettlement = {
          id: tempId("set"),
          trip_id: tripId,
          from_attendee_id: body.from_attendee_id,
          to_attendee_id: body.to_attendee_id,
          amount: body.amount,
          currency: body.currency.toUpperCase(),
          fx_rate_to_base: null,
          settled_at: new Date().toISOString(),
          transaction_id: body.transaction_id ?? null,
          write_off: false,
          created_at: new Date().toISOString(),
        };
        qc.setQueryData<TripDetail>(tripKey(tripId), {
          ...prev,
          settlements: [placeholder, ...prev.settlements],
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(tripKey(tripId), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

// ---------------------------------------------------------------------------
// Invite link mutations (response carries the new token; cache holds nothing)
// ---------------------------------------------------------------------------

export function useGenerateInviteLink(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => tripsApi.generateInviteLink(tripId),
    onSuccess: () => qc.invalidateQueries({ queryKey: tripKey(tripId) }),
  });
}

export function useRevokeInviteLink(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => tripsApi.revokeInviteLink(tripId),
    onSuccess: () => qc.invalidateQueries({ queryKey: tripKey(tripId) }),
  });
}

export function useJoinTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => tripsApi.joinViaToken(token),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: TRIPS_KEY });
      qc.invalidateQueries({ queryKey: tripKey(data.id) });
    },
  });
}

export function useTripPreview(token: string | null) {
  return useQuery({
    queryKey: ["trip-preview", token],
    queryFn: () =>
      token
        ? tripsApi.previewByToken(token)
        : Promise.reject(new Error("no token")),
    enabled: !!token,
    // 404 → bad/expired link. Don't retry; surface immediately.
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// Suggestions inbox mutations
// ---------------------------------------------------------------------------

export function useSuggestedTransactions(tripId: string | null) {
  return useQuery({
    queryKey: tripId ? suggestedKey(tripId) : ["trips", "null", "suggested"],
    queryFn: () =>
      tripId
        ? tripsApi.suggestedTransactions(tripId)
        : Promise.reject(new Error("no id")),
    enabled: !!tripId,
  });
}

export function useDismissSuggestion(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transactionId: string) =>
      tripsApi.dismissSuggestion(tripId, transactionId),
    onMutate: async (transactionId) => {
      await qc.cancelQueries({ queryKey: suggestedKey(tripId) });
      const prev = qc.getQueryData<SuggestedTransaction[]>(suggestedKey(tripId));
      if (prev) {
        qc.setQueryData<SuggestedTransaction[]>(
          suggestedKey(tripId),
          prev.filter((s) => s.transaction_id !== transactionId),
        );
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(suggestedKey(tripId), ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: suggestedKey(tripId) }),
  });
}

export function useUndismissSuggestion(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transactionId: string) =>
      tripsApi.undismissSuggestion(tripId, transactionId),
    onSettled: () => qc.invalidateQueries({ queryKey: suggestedKey(tripId) }),
  });
}

export function useConfirmSettlementSuggestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ConfirmSettlementSuggestionInput) =>
      tripsApi.confirmSettlementSuggestion(body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: tripKey(body.trip_id) });
      await qc.cancelQueries({ queryKey: suggestedKey(body.trip_id) });
      const prevTrip = qc.getQueryData<TripDetail>(tripKey(body.trip_id));
      const prevSuggested = qc.getQueryData<SuggestedTransaction[]>(
        suggestedKey(body.trip_id),
      );
      if (prevTrip) {
        const placeholder: TripSettlement = {
          id: tempId("set"),
          trip_id: body.trip_id,
          from_attendee_id: body.from_attendee_id,
          to_attendee_id: body.to_attendee_id,
          amount: body.amount,
          currency: body.currency.toUpperCase(),
          fx_rate_to_base: null,
          settled_at: new Date().toISOString(),
          transaction_id: body.transaction_id,
          write_off: false,
          created_at: new Date().toISOString(),
        };
        qc.setQueryData<TripDetail>(tripKey(body.trip_id), {
          ...prevTrip,
          settlements: [placeholder, ...prevTrip.settlements],
        });
      }
      if (prevSuggested) {
        qc.setQueryData<SuggestedTransaction[]>(
          suggestedKey(body.trip_id),
          prevSuggested.filter((s) => s.transaction_id !== body.transaction_id),
        );
      }
      return { prevTrip, prevSuggested, tripId: body.trip_id };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prevTrip)
        qc.setQueryData(tripKey(ctx.tripId), ctx.prevTrip);
      if (ctx?.prevSuggested)
        qc.setQueryData(suggestedKey(ctx.tripId), ctx.prevSuggested);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: TRIPS_KEY });
    },
  });
}

export function useDismissSettlementSuggestion() {
  return useMutation({
    mutationFn: (transactionId: string) =>
      tripsApi.dismissSettlementSuggestion(transactionId),
  });
}
