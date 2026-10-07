"""Registers every module's tables on SQLModel.metadata so Alembic can see them.

One Alembic history for the whole app. Add one import line here when a module
gets its first model.
"""
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.tenancy import models as tenancy_models  # noqa: F401
