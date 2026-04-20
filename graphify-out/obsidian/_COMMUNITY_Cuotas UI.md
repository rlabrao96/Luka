---
type: community
cohesion: 0.33
members: 6
---

# Cuotas UI

**Cohesion:** 0.33 - loosely connected
**Members:** 6 nodes

## Members
- [[MarkAsCuotaDialog()]] - code - frontend/app/(dashboard)/components/MarkAsCuotaDialog.tsx
- [[MarkAsCuotaDialog.tsx]] - code - frontend/app/(dashboard)/components/MarkAsCuotaDialog.tsx
- [[useCancelCuota()]] - code - frontend/app/lib/hooks/useCuotas.ts
- [[useCreateCuota()]] - code - frontend/app/lib/hooks/useCuotas.ts
- [[useCuotas()]] - code - frontend/app/lib/hooks/useCuotas.ts
- [[useCuotas.ts]] - code - frontend/app/lib/hooks/useCuotas.ts

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Cuotas_UI
SORT file.name ASC
```
