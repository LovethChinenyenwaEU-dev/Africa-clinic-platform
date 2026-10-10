# How the backend fits together

## The journey of a guarded request

1. A request arrives with `Authorization: Bearer <token>`.
2. The guard (`get_current_staff`) checks the token's signature and expiry.
3. It looks the person up in the database. They must exist, be active, and belong to the clinic written on the token.
4. If the door declares a capability, `require(...)` checks the person's *current* role against the permission table.
5. The endpoint takes the clinic from `current_staff.tenant_id`, never from the request.
6. Service functions read data through `tenant_select` / `get_in_tenant`.
7. A response schema filters what is allowed to leave (no password hashes).

## Each module's public door

| Module | What other code may import |
|---|---|
| identity | `service.py`, `dependencies.py` (`get_current_staff`, `CurrentStaff`, `require`), `permissions.py` (`Capability`) |
| tenancy | `service.py` |
| core | `tenant_scope.py`, `events.py`, `db.py`, `config.py` |

Routers, repositories and models are internal to their module.

## Rules we follow

- The clinic always comes from the guard, never from the address or the form.
- Another clinic's data answers 404, exactly like a missing ID.
- 401 means "who are you?" and 403 means "I know who you are, and no."
- Doors ask for capabilities, not job titles. Unknown roles get nothing.
- The database wins over the token: role and active status are read fresh on every request.
- People are switched off, never deleted.
- Check everything that can fail before saving anything.
- Every failure at login looks the same from outside.
- Anything that changes data is a POST (or PUT/PATCH/DELETE), never a GET.

## Known limits (to fix later)

- No limit on login attempts yet (Redis is the planned tool).
- Two admins switching each other off at the same instant could slip past the last-admin check; needs a database lock.
- The clinic and its first admin are created in two saves; one transaction would be safer.
- New staff get a password chosen by the admin; add "change on first login".
- Emails are unique across all clinics and are not yet checked for shape.
- Tenant isolation is one lock (our query helpers). A second lock inside the database (row-level security) is planned.
- HTTPS and secret management are deployment tasks, not done yet.