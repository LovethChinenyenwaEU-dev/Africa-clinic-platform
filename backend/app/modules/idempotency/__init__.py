"""Idempotency keys: a write sent twice (a retry, an offline outbox replay) happens once.

Public door: service.py. The HTTP side lives in middleware.py and is added in app/main.py.
"""
