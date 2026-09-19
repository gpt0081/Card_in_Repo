from __future__ import annotations

from .app import _STORE, app
from .auth import auth_settings_from_env, create_auth_router
from .learning import create_learning_router

# Authentication is additive: public repository analysis remains anonymous-first.
# Learner state is different: it is always scoped to a verified signed GitHub session.
settings = auth_settings_from_env()
app.include_router(create_auth_router(settings))
app.include_router(create_learning_router(settings, _STORE))

__all__ = ["app"]
