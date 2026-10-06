---
name: clinic-tenant-isolation-rbac
description: How to enforce multi-tenant data isolation and role-based access in the Clinic Platform. Use whenever creating or changing any model, query, endpoint, dependency, permission, login flow, role or test that touches clinic, branch, staff or patient data, and whenever the user mentions tenants, branches, roles, permissions, access control, "can user X see Y", or data leaking between clinics.
---

# Tenant isolation and RBAC

A clinic must never see another clinic's data. Treat any missing tenant filter as a security bug.

## Model rules
- Every tenant-owned table has `tenant_id` (non-null, indexed). Branch-owned tables also have `branch_id`.
- Add `created_by`, `created_at`, `updated_by`, `updated_at`, and `version` to clinical tables.
- Use UUID primary keys.

## Query rules
1. Never query a tenant-owned table without a tenant filter. Use the shared helper (e.g. `tenant_scoped(session, Model, ctx)`) rather than raw `select(Model)`.
2. `tenant_id` comes from the authenticated token/context, **never from request body or query params**.
3. When loading by ID, filter by both ID and tenant: a wrong-tenant ID returns 404, not 403 (do not reveal existence).
4. Back it up in the database with PostgreSQL row-level security policies keyed on a per-request setting; the app layer and database layer should both enforce isolation.
5. Background jobs must carry the tenant context explicitly and set it before touching data.

## Roles (least privilege)
| Role | Typical access |
|---|---|
| admin | Clinic setup, staff, reports, audit view |
| front_desk | Register patients, scheduling, payments; no clinical notes |
| nurse | Vitals, notes, drafts |
| doctor | Full clinical record, prescriptions, referrals, teleconsults |
| billing | Invoices, payments, reconciliation; no clinical notes |

Implement permissions as named capabilities (e.g. `patient:read`, `encounter:write`, `refund:approve`) mapped from roles, and check capabilities in route dependencies, not inline role strings. Refund approval must be a different user from the requester.

## Auth
- Short-lived access tokens; refresh with rotation; ability to revoke sessions and devices.
- MFA for admin, doctor and billing roles where feasible.
- Hash passwords with a modern algorithm; never log credentials or tokens.

## Tests (required for every new patient-data endpoint)
```python
def test_cross_tenant_read_returns_404(client, tenant_a_user, tenant_b_patient): ...
def test_cross_tenant_list_excludes_other_tenant(client, tenant_a_user): ...
def test_role_without_capability_is_forbidden(client, front_desk_user, encounter): ...
```
Add a test that enumerates all routes and fails if a route touching tenant data lacks the scoping dependency.

## Common mistakes to avoid
- Trusting a `tenant_id` sent by the client
- Joining tables without carrying the tenant filter through
- Caching responses without the tenant in the cache key
- Admin or support tooling that bypasses scoping without an audit event
