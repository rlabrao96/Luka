# Bank Scraper — Project State & Next Steps

> Prompt document for continuing work on the bank scraper in a separate terminal.
> Generated: 2026-03-26

---

## What We Built

A modified fork of [open-banking-chile](https://github.com/kaihv/open-banking-chile) that scrapes **Banco de Chile** with significant enhancements over the original. The fork lives at `test-scraper/open-banking-chile-fork/`.

### What Works (Banco de Chile)

| Feature | Status | Method |
|---------|--------|--------|
| Login + 2FA handling | ✓ | Puppeteer headful |
| Account balances (CLP, USD, Line of Credit) | ✓ | Internal REST API |
| Checking account movements (CLP) — last 45 days | ✓ | Internal REST API (`getCartola`) |
| Checking account movements (CLP) — 3 months | ✓ | HTML table scraping + calendar UI interaction |
| Checking account movements (USD) | ✓ | Internal REST API |
| Credit card cupos (nacional + internacional) | ✓ | Internal REST API |
| Credit card unbilled movements | ✓ | Internal REST API |
| Credit card billed movements — 3 months | ✓ | Internal REST API (3 billing periods) |
| Currency tagging (CLP/USD per movement) | ✓ | Added by us |
| Account tagging (account number + name) | ✓ | Added by us |
| Transaction time (HH:MM) for checking | ✓ | Extracted from `fecha` field |
| **Total movements in test run** | **301** | |

### Key Files

```
test-scraper/
├── test_bchile.py                    # Python test script (prompts for creds, runs scraper, displays results)
├── last_result.json                  # Raw JSON from last run
├── last_debug.log                    # Debug log from last run
├── screenshots/                      # Screenshots from historical scraping
├── open-banking-chile-fork/          # Our modified fork
│   ├── src/banks/bchile.ts           # Main Banco de Chile scraper (heavily modified)
│   ├── src/types.ts                  # Added: currency, accountNumber, accountName, time fields
│   └── dist/                         # Built output (run `npx tsup ... --no-dts` to rebuild)
├── node_modules/                     # Original npm package (unused now, using fork)
└── package.json
```

### How to Build & Run

```bash
# Build the fork after changes
cd test-scraper/open-banking-chile-fork
npx tsup src/cli.ts src/index.ts --format esm,cjs --target es2022 --clean --no-dts

# Run the test
cd test-scraper
python3 test_bchile.py
# Prompts for RUT + password, opens Chrome headful, takes ~2-3 min
```

### Architecture of Our bchile.ts Modifications

1. **Current movements (API)**: Calls `getCartola` endpoint — returns last 45 days with full JSON (date, time, amount, description, balance, sender/recipient)
2. **Historical movements (HTML scrape)**: For each additional 45-day window:
   - Navigates to home → saldos-movimientos (forces account selector modal)
   - Handles modal: selects CLP currency, clicks radio button, clicks ACEPTAR
   - Clicks FILTRAR to expand filter panel
   - Opens calendar picker (clicks 📅 icon), navigates months with `<` arrow, picks start day, navigates forward with `>`, picks end day
   - Clicks APLICAR FILTROS
   - Scrapes HTML table rows (Fecha, Descripción, Canal, Cargos, Abono, Saldo)
   - Paginates through table pages (clicks `>` at bottom, 10 rows per page)
3. **Credit card unbilled (API)**: `tarjeta-credito-digital/movimientos-no-facturados`
4. **Credit card billed (API)**: `tarjetas/estadocuenta/fechas-facturacion` → iterates last 3 billing periods → `nacional/resumen-por-fecha` + `internacional/resumen-por-fecha`
5. **Balances (API)**: `bff-pp-prod-ctas-saldos/productos/cuentas/saldos`

### Bank Internal API Endpoints (Banco de Chile)

```
Base: https://portalpersonas.bancochile.cl/mibancochile/rest/persona

# Products & client
GET  selectorproductos/selectorProductos/obtenerProductos?incluirTarjetas=true
GET  bff-ppersonas-clientes/clientes/

# Balances
GET  bff-pp-prod-ctas-saldos/productos/cuentas/saldos

# Account movements (last 45 days)
POST movimientos/getConfigConsultaMovimientos  body: { cuentasSeleccionadas: [...] }
POST bff-pper-prd-cta-movimientos/movimientos/getCartola  body: { cuentaSeleccionada, cabecera: { paginacionDesde: 1 } }

# Credit card info
POST tarjetas/widget/informacion-tarjetas
POST tarjeta-credito-digital/saldo/obtener-saldo
POST tarjeta-credito-digital/movimientos-no-facturados

# Credit card billed statements
POST tarjetas/estadocuenta/fechas-facturacion
POST tarjetas/estadocuenta/nacional/resumen-por-fecha
POST tarjetas/estadocuenta/internacional/resumen-por-fecha
```

### Movement Object (our enhanced format)

```json
{
  "date": "18-03-2026",
  "time": "13:36",
  "description": "Abono Api En Linea:775009764",
  "amount": 23654,
  "balance": 154277,
  "source": "account",
  "currency": "CLP",
  "accountNumber": "****7502",
  "accountName": "Cuenta Corriente Moneda Local"
}
```

Sources: `account`, `credit_card_unbilled`, `credit_card_billed`

---

## What Needs to Be Built Next

### 1. Bank Scraper API (Python/FastAPI)

Build a standalone API service that wraps the scraper:

```
POST /api/scrape
  Body: { bank: "bchile", rut: "...", password: "..." }
  Response: { success, movements[], balances{}, creditCards[] }
```

**Key decisions:**
- Run Chrome/Puppeteer in Docker container
- Credentials: encrypt at rest (AES-256), decrypt only at scrape time
- 2FA handling: WebSocket relay to frontend popup (user approves on phone)
- Rate limit: max 1 scrape per hour per account (avoid bank lockout)

### 2. Credential Popup (Frontend)

Build a Fintoc-like widget/modal for users to enter bank credentials:

```
┌─────────────────────────────────┐
│  Conectar Banco de Chile        │
│                                 │
│  RUT: [_______________]         │
│  Clave Internet: [________]    │
│                                 │
│  [Conectar]                     │
│                                 │
│  🔒 Tus datos están encriptados│
└─────────────────────────────────┘
```

Then show loading state while scraper runs:
```
┌─────────────────────────────────┐
│  Conectando con Banco de Chile  │
│  ████████░░░░░░  60%            │
│                                 │
│  Extrayendo movimientos...      │
│                                 │
│  Si tu banco pide Clave         │
│  Dinámica, apruébala en tu app  │
└─────────────────────────────────┘
```

### 3. Data Consolidation Process

Map scraped movements to Luka's transaction model:

```python
# Scraper movement → Luka transaction
{
  "date": "18-03-2026",           → transaction_date
  "time": "13:36",                → transaction_date (combine with date)
  "description": "Traspaso A:...",→ raw_description → LLM categorization
  "amount": -23654,               → amount_cents (already in cents)
  "currency": "CLP",              → currency
  "source": "account",            → source_type
  "accountNumber": "****7502",    → bank_account FK
}
```

**Deduplication strategy:**
- For checking account: match on `date + description + amount` (same as scraper)
- For credit card: match on `date + description + amount + source`
- Cross-reference with email-parsed transactions to avoid double-counting

### 4. Add More Banks

The fork supports 9 banks. Priority order for Luka:
1. **Banco de Chile** ✓ (done, enhanced)
2. **BCI** — has credit card support in original library
3. **Santander** — has credit card support in original library
4. **Itaú** — has credit card support
5. **Banco Estado** — requires headful mode + Xvfb on server

### 5. Known Limitations

- **Checking account history**: Bank API hard-caps at 45 days. HTML scraping extends to ~3 months but is slower (~2-3 min for full scrape)
- **Credit card time**: Bank doesn't provide transaction time for credit card movements (always midnight)
- **Mastercard Black**: `fechas-facturacion` API returns HTTP 300 — likely because it's an "adicional" (secondary) card. Only the titular Visa works for billed statements
- **2FA**: Must be approved manually by the user. Cannot be automated.
- **Bank website changes**: HTML scraping will break when they update their portal. API calls are more stable.
- **Headful Chrome required**: Some banks (BancoEstado) block headless. Banco de Chile works headless but we use headful for the calendar interaction.

---

## Quick Reference

### Rebuild after code changes
```bash
cd test-scraper/open-banking-chile-fork
npx tsup src/cli.ts src/index.ts --format esm,cjs --target es2022 --clean --no-dts
```

### Run test
```bash
cd test-scraper
python3 test_bchile.py
```

### Check results
```bash
cat test-scraper/last_debug.log    # Step-by-step scraper log
cat test-scraper/last_result.json  # Raw JSON output
ls test-scraper/screenshots/       # Visual debugging screenshots
```

### Key source files to edit
- `test-scraper/open-banking-chile-fork/src/banks/bchile.ts` — Banco de Chile scraper
- `test-scraper/open-banking-chile-fork/src/types.ts` — Movement/Account types
- `test-scraper/test_bchile.py` — Python test wrapper
