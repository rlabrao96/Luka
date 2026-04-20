---
type: community
cohesion: 0.10
members: 36
---

# Cuotas (Installments)

**Cohesion:** 0.10 - loosely connected
**Members:** 36 nodes

## Members
- [[Add N months to date d, snapping to day=1 semantics.      The cuotas schema enfo]] - rationale - backend/modules/budgets/cuota_service.py
- [[Aggregate active cuotas for a month, scoped personal or household.      Returns]] - rationale - backend/modules/budgets/cuota_service.py
- [[Cancel a cuota. Returns {ok true} on success.      Returns a JSON body (not 2]] - rationale - backend/modules/budgets/cuota_router.py
- [[Create a cuota record. Derives monthly_amount and last_cuota_date.      - `month]] - rationale - backend/modules/budgets/cuota_service.py
- [[CuotaCreateRequest]] - code - backend/modules/budgets/cuota_schemas.py
- [[CuotaListResponse]] - code - backend/modules/budgets/cuota_schemas.py
- [[CuotaResponse]] - code - backend/modules/budgets/cuota_schemas.py
- [[Cuotas (installment purchases) service layer.  Chunk C owns only the read-side a]] - rationale - backend/modules/budgets/cuota_service.py
- [[Mark a cuota cancelled. Only the owner (user_id) can cancel.      Raises LookupE]] - rationale - backend/modules/budgets/cuota_service.py
- [[One cuota row as exposed via the API.]] - rationale - backend/modules/budgets/cuota_schemas.py
- [[Payload for POST cuotas — marks a purchase as an installment plan.      The ser]] - rationale - backend/modules/budgets/cuota_schemas.py
- [[Pydantic schemas for the cuotas REST surface (Chunk E).  Kept isolated from `v2_]] - rationale - backend/modules/budgets/cuota_schemas.py
- [[REST surface for cuotas (installment purchases) — Chunk E.  - POST   cuotas]] - rationale - backend/modules/budgets/cuota_router.py
- [[Return (first_day, last_day) for the given month.      `month` is expected to al]] - rationale - backend/modules/budgets/cuota_service.py
- [[Return all active cuotas scoped to a user (personal) or household.      Rows com]] - rationale - backend/modules/budgets/cuota_service.py
- [[Return the first active household_id for the current user.      Raises 404 if th]] - rationale - backend/modules/budgets/cuota_router.py
- [[_add_months()]] - code - backend/modules/budgets/cuota_service.py
- [[_get_first_household_id()]] - code - backend/tests/test_cuota_service.py
- [[_get_seed_user()_3]] - code - backend/tests/test_cuota_service.py
- [[_month_bounds()]] - code - backend/modules/budgets/cuota_service.py
- [[_user_active_household_id()]] - code - backend/modules/budgets/cuota_router.py
- [[cancel_cuota()]] - code - backend/modules/budgets/cuota_service.py
- [[create_cuota()]] - code - backend/modules/budgets/cuota_service.py
- [[cuota_router.py]] - code - backend/modules/budgets/cuota_router.py
- [[cuota_schemas.py]] - code - backend/modules/budgets/cuota_schemas.py
- [[cuota_service.py]] - code - backend/modules/budgets/cuota_service.py
- [[delete_cuota()]] - code - backend/modules/budgets/cuota_router.py
- [[get_active_cuotas_summary()]] - code - backend/modules/budgets/cuota_service.py
- [[get_cuotas()]] - code - backend/modules/budgets/cuota_router.py
- [[list_active_cuotas()]] - code - backend/modules/budgets/cuota_service.py
- [[post_cuota()]] - code - backend/modules/budgets/cuota_router.py
- [[test_cancel_cuota_sets_status_cancelled()]] - code - backend/tests/test_cuota_service.py
- [[test_create_cuota_persists_with_computed_fields()]] - code - backend/tests/test_cuota_service.py
- [[test_cuota_service.py]] - code - backend/tests/test_cuota_service.py
- [[test_list_active_cuotas_scopes_to_user()]] - code - backend/tests/test_cuota_service.py
- [[test_month_boundary_cuota_last_month_active_this_month()]] - code - backend/tests/test_cuota_service.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Cuotas_(Installments)
SORT file.name ASC
```

## Connections to other communities
- 16 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 3 edges to [[_COMMUNITY_Pydantic Schemas]]
- 1 edge to [[_COMMUNITY_Budgets (v2 v3)]]

## Top bridge nodes
- [[create_cuota()]] - degree 8, connects to 1 community
- [[test_cuota_service.py]] - degree 7, connects to 1 community
- [[test_month_boundary_cuota_last_month_active_this_month()]] - degree 6, connects to 1 community
- [[CuotaCreateRequest]] - degree 6, connects to 1 community
- [[CuotaResponse]] - degree 6, connects to 1 community