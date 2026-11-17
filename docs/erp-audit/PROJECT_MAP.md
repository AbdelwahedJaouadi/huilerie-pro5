# Oro Verde ERP — Project Map (Initial Audit)

Audit target: `abdelwehed-hue/huilerie-pro5`  
Branch inspected: `main`  
Audit branch: `audit/erp-foundation`  
Scope: static source review only; no application, database, or Render configuration changes.

## Technology

- Backend: FastAPI, Python, Motor/PyMongo, Pydantic.
- Frontend: React 19, Vite, TypeScript, TanStack Query.
- Persistence: MongoDB selected through `MONGO_URL` and `DB_NAME` in `backend/lib/db.py`.
- Hosting configuration is not verified by this source audit.

## Application entry points

- `backend/server.py`: creates the FastAPI app, mounts the `/api` router, and registers authentication, loads, lab, admin, extras, campaign, TV, invoices, client accounts, accounting, and commercial routers.
- `frontend/src/App.tsx`: route table for the main application, commercial management, accounting, audit, TV, invoices, and other screens.
- `frontend/src/components/AppShell.tsx`: primary navigation and commercial header navigation.
- `backend/lib/db.py`: shared MongoDB client/database handle and core index creation.
- `backend/lib/auth.py` and `backend/lib/security_config.py`: session/authentication and production security checks.

## Existing business domains

| Domain | Main implementation | Initial observation |
|---|---|---|
| Reception / loads | `backend/routers/loads.py` | Load creation, list/search, oil result, status, delivery, cancellation, deletion, statistics |
| Laboratory | `backend/routers/lab.py` | Analyses linked to loads |
| Traditional invoices | `backend/routers/invoices.py` | Invoice creation/update/list and deletion controls tied to source loads |
| Client statements | `backend/routers/client_accounts.py` | Consolidated client history and statements |
| Commercial / GS | `backend/commercial/routers.py` | Purchases, suppliers, lots, stock, tanks, quality, production, sales, payments, returns, custody, audit |
| Accounting overview | `backend/routers/accounting.py` | Source-document aggregation and daily cash/accrual-style report; not a double-entry ledger |
| TV | `backend/routers/tv.py` | Display/media settings, music, control, board and administration |
| Audit | Commercial audit endpoints and `frontend/src/pages/Audit.tsx` | Stronger coverage in GS than in the traditional mill flows |

## Frontend routes confirmed

- `/`, `/intake`, `/search`, `/loads`, `/lab`, `/settings`, `/clients`, `/reports`
- `/factures`, `/comptabilite`, `/commercial`, `/audit`
- `/tv`, `/tv-admin`, `/sms`, `/cancellations`, certificate routes, login and help.

## Key architectural observation

The commercial router imports `client`, `db`, and `run_transaction` from `lib.db`, the same module used by the main Oro Verde API. The actual implementation therefore uses the same configured MongoDB client and database handle. The docstring in `backend/commercial/__init__.py` says “dedicated database”, which conflicts with the implementation and must be corrected in project documentation or architecture if it is not intentional.

## Known audit limitations

This is not yet a complete route-by-route or collection-by-collection inventory. The GitHub source was inspected, but no live MongoDB connection, Render environment values, production logs, or browser session was inspected. Runtime collection counts, actual `DB_NAME`, live deployment health, and real-user permissions remain unverified.
