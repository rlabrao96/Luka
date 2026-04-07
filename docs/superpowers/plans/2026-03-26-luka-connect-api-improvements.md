# Luka Connect API Improvements (8.1–8.4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the Luka Connect scraping API so that CC movements are tagged with their card label, the `days_back` parameter controls how far back to scrape, and the callback field name matches what the backend expects (`allBalances` not `balances`).

**Architecture:** Four surgical changes to the existing scraper codebase — add a `cardLabel` field to movements, thread `days_back` from the API endpoint through to the scraper logic, use it to control the number of HTML-scraping windows, and fix the callback payload field name. No new files, no new dependencies.

**Tech Stack:** Node.js, Express, TypeScript, Puppeteer (headless Chrome)

**Repo:** `luka-connect` at `/Users/rlabrao/Documents/Proyectos AI/luka-connect`

**Design Spec:** `docs/superpowers/specs/2026-03-26-luka-connect-accounts-balances-design.md` (section 8)

---

## File Map

### Modify

| File | Responsibility |
|------|---------------|
| `src/types.ts:19-41` | Add `cardLabel` field to `BankMovement` interface |
| `src/types.ts:97-109` | Add `daysBack` to `ScraperOptions` interface |
| `src/banks/bchile.ts:818-823` | Tag unbilled CC movements with `cardLabel` |
| `src/banks/bchile.ts:854-865` | Tag billed CC movements with `cardLabel` |
| `src/banks/bchile.ts:249` | Accept `daysBack` in `fetchAccountMovements()` |
| `src/banks/bchile.ts:287-293` | Use `daysBack` to calculate number of HTML windows |
| `src/banks/bchile.ts:878-881` | Read `daysBack` from options, pass to `fetchAccountMovements()` |
| `src/scraper.ts:4-8` | Add `daysBack` to `ScrapeRequest` interface |
| `src/scraper.ts:17-20` | Pass `daysBack` into `bank.scrape()` options |
| `src/index.ts:16` | Destructure `days_back` from request body |
| `src/index.ts:26,43` | Pass `days_back` to `runScrape()` |
| `src/index.ts:50` | Fix callback: rename `balances` → `allBalances` |

---

## Task 1: Add `cardLabel` Field to BankMovement Type

**Files:**
- Modify: `src/types.ts:19-41`

- [ ] **Step 1: Add the field to the interface**

In `src/types.ts`, add `cardLabel` to the `BankMovement` interface after `accountName` (line 39):

```typescript
  /** Etiqueta de tarjeta de crédito (ej: "Visa Signature ****5032") — only for CC movements */
  cardLabel?: string;
```

- [ ] **Step 2: Verify the build compiles**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && npx tsup src/index.ts --format cjs --target es2022 --clean --dts 2>&1 | tail -5
```

Expected: Build succeeds (new optional field is backwards compatible).

- [ ] **Step 3: Commit**

```bash
git add src/types.ts
git commit -m "feat: add cardLabel field to BankMovement type"
```

---

## Task 2: Tag CC Movements with Card Label (8.1 + 8.4)

**Files:**
- Modify: `src/banks/bchile.ts:818-823` (unbilled movements)
- Modify: `src/banks/bchile.ts:854-865` (billed movements)

The `fetchCreditCardData()` function already loops per card and has `cardLabel` available (line 796: `const cardLabel = ...`). The movements just aren't tagged with it.

- [ ] **Step 1: Tag unbilled movements with cardLabel**

In `src/banks/bchile.ts`, find the unbilled movement push (line 822):

```typescript
        movements.push({ date: normalizeDate(mov.fechaTransaccionString), description: (mov.glosaTransaccion || "").trim(), amount, balance: 0, source: MOVEMENT_SOURCE.credit_card_unbilled, installments: normalizeInstallments(mov.despliegueCuotas), currency });
```

Replace with (add `cardLabel`):

```typescript
        movements.push({ date: normalizeDate(mov.fechaTransaccionString), description: (mov.glosaTransaccion || "").trim(), amount, balance: 0, source: MOVEMENT_SOURCE.credit_card_unbilled, installments: normalizeInstallments(mov.despliegueCuotas), currency, cardLabel });
```

- [ ] **Step 2: Tag billed nacional movements with cardLabel**

In `src/banks/bchile.ts`, find the nacional billed push (line 858):

```typescript
              for (const tx of filtered) movements.push(facturadoToMovement(tx, MOVEMENT_SOURCE.credit_card_billed, "CLP"));
```

Replace with:

```typescript
              for (const tx of filtered) movements.push({ ...facturadoToMovement(tx, MOVEMENT_SOURCE.credit_card_billed, "CLP"), cardLabel });
```

- [ ] **Step 3: Tag billed internacional movements with cardLabel**

In `src/banks/bchile.ts`, find the internacional billed push (line 865):

```typescript
              for (const tx of filtered) movements.push(facturadoToMovement(tx, MOVEMENT_SOURCE.credit_card_billed, "USD"));
```

Replace with:

```typescript
              for (const tx of filtered) movements.push({ ...facturadoToMovement(tx, MOVEMENT_SOURCE.credit_card_billed, "USD"), cardLabel });
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && npx tsup src/index.ts --format cjs --target es2022 --clean --dts 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add src/banks/bchile.ts
git commit -m "feat: tag CC movements with cardLabel for per-card linking (8.1 + 8.4)"
```

---

## Task 3: Add `daysBack` to ScraperOptions and ScrapeRequest

**Files:**
- Modify: `src/types.ts:97-109`
- Modify: `src/scraper.ts:4-8, 17-20`

- [ ] **Step 1: Add `daysBack` to ScraperOptions**

In `src/types.ts`, add to the `ScraperOptions` interface (after `onProgress`, line 108):

```typescript
  /** How many days back to fetch movements. Default: 90 (full). 4 = recent only (API, no HTML scrape). */
  daysBack?: number;
```

- [ ] **Step 2: Add `daysBack` to ScrapeRequest in scraper.ts**

In `src/scraper.ts`, replace the `ScrapeRequest` interface (lines 4-8):

```typescript
interface ScrapeRequest {
  bank: string;
  rut: string;
  password: string;
  mode: "full" | "recent";
  daysBack?: number;
}
```

- [ ] **Step 3: Pass `daysBack` into bank.scrape() options**

In `src/scraper.ts`, update the `bank.scrape()` call (lines 17-20):

```typescript
  const result = await bank.scrape({
    rut: req.rut,
    password: req.password,
    daysBack: req.daysBack,
    headful: true,
    onProgress: (step) => console.log(`[${req.bank}] ${step}`),
  });
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && npx tsup src/index.ts --format cjs --target es2022 --clean --dts 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add src/types.ts src/scraper.ts
git commit -m "feat: add daysBack parameter to ScraperOptions and ScrapeRequest"
```

---

## Task 4: Thread `days_back` from API Endpoint

**Files:**
- Modify: `src/index.ts:16, 26, 43`

- [ ] **Step 1: Destructure `days_back` from request body and validate**

In `src/index.ts`, update line 16:

```typescript
  const { bank, rut, password, mode, callbackUrl, jobId, days_back } = req.body;
  const daysBack = typeof days_back === "number" && days_back > 0 ? days_back : undefined;
```

- [ ] **Step 2: Pass to runScrape in sync mode (line 26)**

Replace:

```typescript
      const result = await runScrape({ bank, rut, password, mode: mode || "full" });
```

With:

```typescript
      const result = await runScrape({ bank, rut, password, mode: mode || "full", daysBack });
```

- [ ] **Step 3: Pass to runScrape in async mode (line 43)**

Replace:

```typescript
      const result = await runScrape({ bank, rut, password, mode: mode || "recent" });
```

With:

```typescript
      const result = await runScrape({ bank, rut, password, mode: mode || "recent", daysBack });
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && npx tsup src/index.ts --format cjs --target es2022 --clean --dts 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add src/index.ts
git commit -m "feat: thread days_back from /scrape endpoint to scraper options"
```

---

## Task 5: Use `daysBack` in Banco de Chile Scraper

**Files:**
- Modify: `src/banks/bchile.ts:249, 287-293, 878-881, 940`

This is the core logic change. Currently `fetchAccountMovements()` always does:
- API fetch (last ~45 days) — **always runs**
- 2 HTML windows of 45 days each (days 46–90, 91–135) — **slow, ~4 min**

The `daysBack` parameter controls behavior:
- `daysBack <= 45`: API only, skip HTML scraping entirely (seconds)
- `daysBack <= 90`: API + 1 HTML window (days 46–90)
- `daysBack <= 135` or default: API + 2 HTML windows (current behavior)

- [ ] **Step 1: Add `daysBack` parameter to `fetchAccountMovements()`**

In `src/banks/bchile.ts`, update the function signature (line 249):

```typescript
async function fetchAccountMovements(page: Page, products: ApiProduct[], fullName: string, rut: string, debugLog: string[], daysBack: number = 90): Promise<{ movements: BankMovement[]; balance?: number; balances?: Record<string, number> }> {
```

- [ ] **Step 2: Calculate number of HTML windows from `daysBack`**

In `src/banks/bchile.ts`, replace the hardcoded `for (let w = 1; w <= 2; w++)` loop (line 293):

```typescript
        const numWindows = daysBack <= 45 ? 0 : Math.min(Math.ceil((daysBack - 45) / 45), 2);
        debugLog.push(`    daysBack=${daysBack}, HTML windows to scrape: ${numWindows}`);

        for (let w = 1; w <= numWindows; w++) {
```

This replaces the original line:

```typescript
        for (let w = 1; w <= 2; w++) {
```

- [ ] **Step 3: Pass `daysBack` from scrapeBchile() to fetchAccountMovements()**

In `src/banks/bchile.ts`, update the call to `fetchAccountMovements()` in `scrapeBchile()` (line 940):

```typescript
  const daysBack = options.daysBack ?? 90;
  const acctResult = await fetchAccountMovements(page, products.productos, fullName, products.rut, debugLog, daysBack);
```

This replaces the original line:

```typescript
  const acctResult = await fetchAccountMovements(page, products.productos, fullName, products.rut, debugLog);
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && npx tsup src/index.ts --format cjs --target es2022 --clean --dts 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add src/banks/bchile.ts
git commit -m "feat: use daysBack to control HTML scraping windows (8.3) — <=45 days uses API only"
```

---

## Task 6: Fix Callback Field Name (`balances` → `allBalances`)

**Files:**
- Modify: `src/index.ts:50`

Currently the async callback sends `balances: result.allBalances` (line 50). The Luka backend's `ConnectCallback` model expects `allBalances`. This mismatch means the backend currently receives the data under the wrong key.

- [ ] **Step 1: Fix the field name in the callback payload**

In `src/index.ts`, find line 50:

```typescript
          ? { movements: result.movements, balances: result.allBalances, creditCards: result.creditCards }
```

Replace with:

```typescript
          ? { movements: result.movements, allBalances: result.allBalances, creditCards: result.creditCards }
```

- [ ] **Step 2: Verify the build compiles**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && npx tsup src/index.ts --format cjs --target es2022 --clean --dts 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add src/index.ts
git commit -m "fix: rename callback field balances → allBalances to match backend model"
```

---

## Task 7: Build, Verify, and Final Commit

- [ ] **Step 1: Full build**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && npm run build
```

Expected: Clean build, no errors.

- [ ] **Step 2: Verify output types include cardLabel and daysBack**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && grep -n "cardLabel" dist/index.d.ts && grep -n "daysBack" dist/index.d.ts
```

Expected: Both fields appear in the generated type definitions.

- [ ] **Step 3: Spot-check the built JS for days_back threading**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && grep -c "daysBack" dist/index.js && grep -c "cardLabel" dist/index.js
```

Expected: Multiple occurrences of each in the built output.

- [ ] **Step 4: Review all changes**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/luka-connect" && git diff HEAD~6 --stat
```

Expected: 4 files changed: `src/types.ts`, `src/index.ts`, `src/scraper.ts`, `src/banks/bchile.ts`

---

## Summary

| Task | Description | Files | Steps |
|------|-------------|-------|-------|
| 1 | Add `cardLabel` to `BankMovement` type | `types.ts` | 3 |
| 2 | Tag CC movements with card label (8.1 + 8.4) | `bchile.ts` | 5 |
| 3 | Add `daysBack` to `ScraperOptions` + `ScrapeRequest` | `types.ts`, `scraper.ts` | 5 |
| 4 | Thread `days_back` from API endpoint | `index.ts` | 5 |
| 5 | Use `daysBack` in BChile scraper logic (8.3) | `bchile.ts` | 5 |
| 6 | Fix callback field name (8.2 bug) | `index.ts` | 3 |
| 7 | Build verification | — | 4 |
| **Total** | | **4 files** | **30 steps** |

### Mapping to Original Improvements

| Improvement | Covered by |
|-------------|-----------|
| **8.1** Tag CC movements with card label | Tasks 1 + 2 |
| **8.2** API vs HTML scrape strategy | Task 5 (daysBack ≤ 45 → API only, no HTML) |
| **8.3** `days_back` parameter support | Tasks 3 + 4 + 5 |
| **8.4** Per-card movement sections | Tasks 1 + 2 (cardLabel tags each movement with its card) |

### Backend Compatibility Note

After deploying these changes, the Luka backend `ConnectCallback` model needs to be updated:
- Rename `balances` field to `allBalances` (or add `Field(alias="allBalances")`)
- Add `cardLabel` to the movement mapper (`map_movement_to_transaction`)
- The `_ensure_accounts()` plan already handles this — see `docs/superpowers/plans/2026-03-26-luka-connect-accounts-balances.md`
