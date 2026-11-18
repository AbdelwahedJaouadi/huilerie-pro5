# Oro Verde ERP — Project Map (Initial Audit)

Audit target: `abdelwehed-hue/huilerie-pro5`  
Source branch inspected: `main`  
Audit branch: `audit/erp-foundation`  
Scope: source review plus read-only Render and Atlas inspection. No application source, database documents, indexes, environment variables, or deployment settings were changed during the source/runtime audit.

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

Both inspected latest deploys used commit `a4f080bc574251ae841b7b7a153cf1986c5392bd` (17 Nov 2026, TV media synchronization update). The backend service is in Virginia on Render's Free plan, one instance. This confirms the intended pro5 frontend/backend services exist and were marked live at inspection time; it does not prove every user workflow is healthy.

## Database pairing

The user explicitly confirmed that pro5 intentionally uses the existing MongoDB database named `huilerie-pro3`. The code confirms that the traditional API and GS import the same configured MongoDB handle from `backend/lib/db.py`.

Render's service-details response did not expose environment variable values, so the literal secret values were not independently read back. Do not interpret the database name `huilerie-pro3` as a mismatch: it is the user's intended database for the pro5 application.

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
| Accounting overview | `backend/routers/accounting.py` | Source-document aggregation and daily reporting; not a double-entry ledger |
| TV | `backend/routers/tv.py` | Display/media settings, music, control, board and administration |
| Audit | Commercial audit endpoints and `frontend/src/pages/Audit.tsx` | Stronger coverage in GS than in the traditional mill flows |

## Frontend routes confirmed

- `/`, `/intake`, `/search`, `/loads`, `/lab`, `/settings`, `/clients`, `/reports`
- `/factures`, `/comptabilite`, `/commercial`, `/audit`
- `/tv`, `/tv-admin`, `/sms`, `/cancellations`, certificate routes, login and help.

## Key architecture and security observations

- GS and the traditional API share the same configured MongoDB database handle. The docstring in `backend/commercial/__init__.py` incorrectly describes GS as using a dedicated database.
- Production runtime validation rejects `AUTH_DISABLED=true`; preserve this fail-closed guard.
- Traditional load operations such as creation, status changes, oil recording and delivery use authenticated-user access. Invoice mutations and load cancellation/deletion are admin-only in the inspected routes.
- GS has granular commercial permission checks, but the assignable worker permissions are a subset of the full admin permissions. This means some high-impact capabilities remain admin-only today; a complete role matrix is still required.
- The accounting routes inspected so far are admin-only. No accountant-specific role was found in the inspected auth policy.

## Audit limitations

- No production logs, browser journey, or automated test suite execution was performed in this pass.
- The Atlas collection/index snapshot was read-only. Reference integrity and complete collection/index inventories remain in progress.
