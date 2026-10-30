from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.config import settings, DEFAULT_PACKAGES

router = APIRouter(prefix="/api/settings", tags=["settings"])

class UpdateSettingsPayload(BaseModel):
    agent_name: Optional[str] = None
    business_name: Optional[str] = None
    business_email: Optional[str] = None
    business_website: Optional[str] = None
    autonomous_mode: Optional[bool] = None
    min_lead_score: Optional[int] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    discord_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    stripe_payment_link: Optional[str] = None
    paypal_link: Optional[str] = None

@router.get("")
async def get_settings():
    return {
        "agent_name": settings.AGENT_NAME,
        "business_name": settings.BUSINESS_NAME,
        "business_email": settings.BUSINESS_EMAIL,
        "business_website": settings.BUSINESS_WEBSITE,
        "autonomous_mode": settings.AUTONOMOUS_MODE,
        "min_lead_score": settings.MIN_LEAD_SCORE_TO_CONTACT,
        "scan_interval_minutes": settings.SCAN_INTERVAL_MINUTES,
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "has_smtp": bool(settings.SMTP_USER and settings.SMTP_PASSWORD),
        "smtp_host": settings.SMTP_HOST,
        "smtp_user": settings.SMTP_USER,
        "has_discord": bool(settings.DISCORD_WEBHOOK_URL),
        "discord_webhook_url": settings.DISCORD_WEBHOOK_URL,
        "has_telegram": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "telegram_bot_token": settings.TELEGRAM_BOT_TOKEN,
        "telegram_chat_id": settings.TELEGRAM_CHAT_ID,
        "stripe_payment_link": settings.STRIPE_PAYMENT_LINK_BASE,
        "paypal_link": settings.PAYPAL_ME_LINK,
        "packages": {k: v.to_dict() for k, v in DEFAULT_PACKAGES.items()}
    }

@router.post("")
async def update_settings(payload: UpdateSettingsPayload):
    if payload.agent_name is not None:
        settings.AGENT_NAME = payload.agent_name
    if payload.business_name is not None:
        settings.BUSINESS_NAME = payload.business_name
    if payload.business_email is not None:
        settings.BUSINESS_EMAIL = payload.business_email
    if payload.business_website is not None:
        settings.BUSINESS_WEBSITE = payload.business_website
    if payload.autonomous_mode is not None:
        settings.AUTONOMOUS_MODE = payload.autonomous_mode
    if payload.min_lead_score is not None:
        settings.MIN_LEAD_SCORE_TO_CONTACT = payload.min_lead_score
    if payload.gemini_api_key is not None:
        settings.GEMINI_API_KEY = payload.gemini_api_key
    if payload.openai_api_key is not None:
        settings.OPENAI_API_KEY = payload.openai_api_key
    if payload.smtp_user is not None:
        settings.SMTP_USER = payload.smtp_user
        _persist_to_env("SMTP_USER", payload.smtp_user)
    if payload.smtp_password is not None:
        settings.SMTP_PASSWORD = payload.smtp_password
        _persist_to_env("SMTP_PASSWORD", payload.smtp_password)
    if payload.smtp_host is not None:
        settings.SMTP_HOST = payload.smtp_host
        _persist_to_env("SMTP_HOST", payload.smtp_host)
    if payload.smtp_port is not None:
        settings.SMTP_PORT = payload.smtp_port
        _persist_to_env("SMTP_PORT", str(payload.smtp_port))
    if payload.discord_webhook_url is not None:
        settings.DISCORD_WEBHOOK_URL = payload.discord_webhook_url
        _persist_to_env("DISCORD_WEBHOOK_URL", payload.discord_webhook_url)
    if payload.telegram_bot_token is not None:
        clean_token = payload.telegram_bot_token.strip().replace(" ", "")
        if clean_token.startswith("bot"):
            clean_token = clean_token[3:]
        settings.TELEGRAM_BOT_TOKEN = clean_token
        _persist_to_env("TELEGRAM_BOT_TOKEN", clean_token)
    if payload.telegram_chat_id is not None:
        clean_chat_id = payload.telegram_chat_id.strip().replace(" ", "")
        settings.TELEGRAM_CHAT_ID = clean_chat_id
        _persist_to_env("TELEGRAM_CHAT_ID", clean_chat_id)
    if payload.stripe_payment_link is not None:
        settings.STRIPE_PAYMENT_LINK_BASE = payload.stripe_payment_link
        _persist_to_env("STRIPE_PAYMENT_LINK_BASE", payload.stripe_payment_link)
    if payload.paypal_link is not None:
        clean_paypal = payload.paypal_link.strip().replace(" ", "")
        if clean_paypal and not clean_paypal.startswith("http"):
            clean_paypal = f"https://paypal.me/{clean_paypal.replace('@', '')}"
        settings.PAYPAL_ME_LINK = clean_paypal
        _persist_to_env("PAYPAL_ME_LINK", clean_paypal)

    return {"status": "updated", "message": "Settings updated dynamically and saved to disk"}

def _persist_to_env(key: str, val: Any):
    try:
        import os
        from pathlib import Path
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        if not env_file.exists():
            return
        lines = env_file.read_text(encoding="utf-8").splitlines(keepends=True)
        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
                new_lines.append(f'{key}="{val}"\n')
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f'{key}="{val}"\n')
        env_file.write_text("".join(new_lines), encoding="utf-8")
    except Exception:
        pass

class TestTelegramPayload(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

@router.post("/test_telegram")
async def test_telegram(payload: TestTelegramPayload):
    from app.engines.notifier import Notifier
    notifier = Notifier()
    result = await notifier.send_test_telegram(
        token=payload.telegram_bot_token or settings.TELEGRAM_BOT_TOKEN,
        chat_id=payload.telegram_chat_id or settings.TELEGRAM_CHAT_ID
    )
    return result

class TestSmtpPayload(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None

@router.post("/test_smtp")
async def test_smtp(payload: TestSmtpPayload):
    from app.engines.email_engine import EmailEngine
    engine = EmailEngine()
    host = payload.smtp_host or settings.SMTP_HOST
    port = payload.smtp_port or settings.SMTP_PORT
    user = payload.smtp_user or settings.SMTP_USER
    pwd = payload.smtp_password or settings.SMTP_PASSWORD

    if not host or not user or not pwd:
        return {"success": False, "error": "SMTP Host, User Email, and App Password are all required."}

    result = engine.test_connection(host=host, port=port, user=user, password=pwd)
    return result
