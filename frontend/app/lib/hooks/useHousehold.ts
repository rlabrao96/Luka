import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function useHouseholdSummary(currency?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "summary", householdId, currency],
    queryFn: () => api.getHouseholdSummary(householdId!, currency),
    enabled: !!householdId,
  });
}

export function useMemberStats() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "member-stats", householdId],
    queryFn: () => api.getMemberStats(householdId!),
    enabled: !!householdId,
  });
}

export function useCategoryBreakdown(month?: string, currency?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "category-breakdown", householdId, month, currency],
    queryFn: () => api.getCategoryBreakdown(householdId!, month, currency),
    enabled: !!householdId,
  });
}

export function useSettlement(month?: string, currency?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "settlement", householdId, month, currency],
    queryFn: () => api.getSettlement(householdId!, month, currency),
    enabled: !!householdId,
  });
}

export function useSplitRatio() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "split-ratio", householdId],
    queryFn: () => api.getSplitRatio(householdId!),
    enabled: !!householdId,
  });
}

export function useUpdateSplitRatio() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ratio: number[]) => api.updateSplitRatio(householdId!, ratio),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useHouseholdMembers() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "members", householdId],
    queryFn: () => api.getHouseholdMembers(householdId!),
    enabled: !!householdId,
  });
}

export function useCreateAndInvite() {
  const queryClient = useQueryClient();
  const setHousehold = useLukaStore((s) => s.setHousehold);
  return useMutation({
    mutationFn: (email: string) => api.createAndInvite(email),
    onSuccess: (data) => {
      setHousehold(data.household_id);
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useUpdateSettlementEnabled() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => api.updateSettlementEnabled(householdId!, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useRemoveMember() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) => api.removeMember(householdId!, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useUpdateMemberRole() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: string }) =>
      api.updateMemberRole(householdId!, memberId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}
