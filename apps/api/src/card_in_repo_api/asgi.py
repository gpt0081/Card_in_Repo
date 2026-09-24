from __future__ import annotations

from .app import _STORE, app
from .auth import auth_settings_from_env, create_auth_router
from .learning import create_learning_router
from .retrieval import create_retrieval_router
from .runtime import build_concept_index

# Authentication is additive: public repository analysis remains anonymous-first.
# Learner state is different: it is always scoped to a verified signed GitHub session.
settings = auth_settings_from_env()
concept_index = build_concept_index()
app.include_router(create_auth_router(settings))
app.include_router(create_learning_router(settings, _STORE, concept_index))
app.include_router(create_retrieval_router(_STORE, concept_index))

__all__ = ["app"]
