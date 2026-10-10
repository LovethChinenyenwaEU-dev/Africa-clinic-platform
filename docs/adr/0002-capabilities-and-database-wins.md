# ADR-0002: Capabilities, deny by default, and the database wins

- **Status:** Accepted
- **Date:** 2026-10-12

## Context
Staff log in with short-lived tokens. People are hired, fired and promoted while tokens are still valid, and doors will multiply as features are added.

## Decision
- Doors check **capabilities** (for example `branch:write`), mapped from roles in one table. Rules change in one place.
- **Unknown or unlisted roles get no capabilities.** A mistake locks a door instead of opening it.
- The token proves who someone was at login. **Every request re-reads the person from the database**, so switching someone off or changing their role takes effect immediately.
- Tokens carry only IDs and the role, never secrets.
- People are **switched off, never deleted**, to preserve history.
- A clinic must always keep at least one active admin.
- A test fails if any `/api/v1` route lacks the login guard and is not on the public list.

## Consequences
- One extra database lookup per request. Acceptable for a clinic system, and cacheable later.
- Adding a role or capability means editing one table, and a test fails if a role is forgotten.
- Public routes are an explicit, reviewed list.