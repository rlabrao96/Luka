# Luka Frontend

Next.js 14 (App Router) dashboard for Luka personal finance.

## Tech Stack

- **Next.js 14** — App Router, SSR for auth, client components for interactivity
- **Tailwind CSS 4** — Custom design tokens (`luka-primary`, `luka-light`, etc.)
- **shadcn/ui** — Button, Card, Tabs, Table, Badge, Avatar, Input, Separator
- **Recharts** — SpendingChart, CategoryDonut, PaceChart
- **TanStack Query** — Server state with 5-min staleTime
- **Zustand** — Client state (userId, householdId), persisted to localStorage
- **Supabase JS** — Auth (Google + Microsoft OAuth)

## Local Development

```bash
cp .env.local.example .env.local   # Set NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_API_URL
npm install
npm run dev                         # http://localhost:3000
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard home — KPIs, spending chart, category donut, recent transactions |
| `/transactions` | Full transaction list with Todos/Personales/Compartidas tabs |
| `/budgets` | Month selector, income, pace chart, allocation editor, waterfall cards |
| `/household` | Partner contribution stats and pie chart |
| `/settings` | Connected bank accounts, sign-out |
| `/login` | Google + Microsoft OAuth buttons |
| `/onboarding/*` | Setup household, connect bank, verify WhatsApp |

## Deployment

Deployed on Vercel. Environment variables configured in Vercel project settings.
