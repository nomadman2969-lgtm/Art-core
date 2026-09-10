"""Runtime Stripe key resolution: env (test/sandbox) by default, admin-saved live keys when mode=live."""
import os
import stripe
from db import db

ENV_SECRET = os.environ["STRIPE_SECRET_KEY"]
ENV_WEBHOOK = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
ENV_PUBLISHABLE = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
ENV_MODE = os.environ.get("STRIPE_MODE", "test")
ONBOARDING_URL = os.environ.get("STRIPE_ONBOARDING_URL", "")

_state = {"mode": ENV_MODE, "webhook_secret": ENV_WEBHOOK, "publishable": ENV_PUBLISHABLE}


async def apply_stripe_keys() -> dict:
    s = await db.settings.find_one({"id": "global"}) or {}
    mode = s.get("stripe_mode") or ENV_MODE
    live_key = s.get("stripe_live_secret_key")
    if mode == "live" and live_key:
        stripe.api_key = live_key
        _state.update(mode="live", webhook_secret=s.get("stripe_live_webhook_secret") or ENV_WEBHOOK,
                      publishable=s.get("stripe_live_publishable_key") or ENV_PUBLISHABLE)
    else:
        stripe.api_key = ENV_SECRET
        _state.update(mode="test", webhook_secret=ENV_WEBHOOK, publishable=ENV_PUBLISHABLE)
    return dict(_state)


def webhook_secret() -> str:
    return _state["webhook_secret"]


def current_mode() -> str:
    return _state["mode"]


def mask(key: str) -> str:
    if not key:
        return ""
    return f"{key[:7]}…{key[-4:]}" if len(key) > 12 else "••••"
