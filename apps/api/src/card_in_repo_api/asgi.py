from __future__ import annotations

from .app import app
from .auth import auth_settings_from_env, create_auth_router

# Authentication is additive: public repository analysis remains anonymous-first.
# When OAuth settings are absent the session endpoint reports login unavailable and
# the rest of the product path keeps working unchanged.
app.include_router(create_auth_router(auth_settings_from_env()))

__all__ = ["app"]
