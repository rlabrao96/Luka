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
} from "@/app/lib/api";

const TRIPS_KEY = ["trips"] as const;
const tripKey = (id: string) => ["trips", id] as const;
const suggestedKey = (id: string) => ["trips", id, "suggested-transactions"] as const;

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

export function useCreateTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateTripInput) => tripsApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

export function useUpdateTrip(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateTripInput) => tripsApi.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TRIPS_KEY });
      qc.invalidateQueries({ queryKey: tripKey(id) });
    },
  });
}

export function useArchiveTrip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tripsApi.archive(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: TRIPS_KEY }),
  });
}

export function useAddAttendee(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateAttendeeInput) =>
      tripsApi.addAttendee(tripId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: tripKey(tripId) }),
  });
}

export function useRemoveAttendee(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (attendeeId: string) =>
      tripsApi.removeAttendee(tripId, attendeeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: tripKey(tripId) }),
  });
}

export function useForceRemoveAttendee(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (attendeeId: string) =>
      tripsApi.forceRemoveAttendee(tripId, attendeeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: tripKey(tripId) }),
  });
}

export function useCreateExpense(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateExpenseInput) =>
      tripsApi.createExpense(tripId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: tripKey(tripId) });
      qc.invalidateQueries({ queryKey: suggestedKey(tripId) });
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
    onSuccess: () => qc.invalidateQueries({ queryKey: tripKey(tripId) }),
  });
}

export function useDeleteExpense(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (expenseId: string) =>
      tripsApi.deleteExpense(tripId, expenseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: tripKey(tripId) });
      qc.invalidateQueries({ queryKey: suggestedKey(tripId) });
    },
  });
}

export function useCreateSettlement(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateSettlementInput) =>
      tripsApi.createSettlement(tripId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: tripKey(tripId) }),
  });
}

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
    onSuccess: () => qc.invalidateQueries({ queryKey: suggestedKey(tripId) }),
  });
}

export function useUndismissSuggestion(tripId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transactionId: string) =>
      tripsApi.undismissSuggestion(tripId, transactionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: suggestedKey(tripId) }),
  });
}

export function useConfirmSettlementSuggestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ConfirmSettlementSuggestionInput) =>
      tripsApi.confirmSettlementSuggestion(body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: tripKey(vars.trip_id) });
      qc.invalidateQueries({ queryKey: suggestedKey(vars.trip_id) });
    },
  });
}

export function useDismissSettlementSuggestion() {
  return useMutation({
    mutationFn: (transactionId: string) =>
      tripsApi.dismissSettlementSuggestion(transactionId),
  });
}
