# Oro Verde ERP — Project Map (Initial Audit)

Audit target: `abdelwehed-hue/huilerie-pro5`  
Source branch inspected: `main`  
Audit branch: `audit/erp-foundation`  
Scope: source review plus read-only Render and Atlas inspection. No application source, database documents, indexes, environment variables, or deployment settings were changed.

## Technology

- Backend: FastAPI, Python, Motor/PyMongo, Pydantic.
- Frontend: React 19, Vite, TypeScript, TanStack Query.
- Persistence: MongoDB selected through `MONGO_URL` and `DB_NAME` in `backend/lib/db.py`.

## Confirmed Render services

In the Render workspace named `Oroverde`:

| Service | Repository | Branch | Latest inspected state |
|---|---|---|---|
| `oro-verde` | `abdelwehed-hue/huilerie-pro5` | `main` | Static frontend deploy is `live` |
| `oroverde-pro5-api` | `abdelwehed-hue/huilerie-pro5` | `main` | Backend deploy is `live` |

Both inspected latest deploys use commit `a4f080bc574251ae841b7b7a153cf1986c5392bd` (17 Nov 2026, TV media synchronization update). The backend service is in Virginia on Render's Free plan, one instance. This confirms the intended pro5 frontend/backend services exist and are currently marked live; it does not prove that every user workflow is healthy.

Render's service-details response did not expose environment variable values. Therefore the active `MONGO_URL` target and `DB_NAME` for `oroverde-pro5-api` remain unverified.

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

The commercial router imports `client`, `db`, and `run_transaction` from `lib.db`, the same module used by the main Oro Verde API. The actual implementation therefore uses the same configured MongoDB client and database handle. The docstring in `backend/commercial/__init__.py` says “dedicated database”, which conflicts with the implementation and should be corrected.

## Audit limitations

- Render tools confirmed service identity and deploy state but did not expose the service's `MONGO_URL` or `DB_NAME`.
- Atlas read-only inspection found a populated database named `huilerie-pro3` in the connected Atlas project. It is not yet proven that the pro5 Render backend connects to this exact cluster/database.
- No production logs, browser journey, or test suite execution was performed in this pass.
