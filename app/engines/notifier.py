import httpx
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger("omnilead.notifier")

class Notifier:
    def __init__(self):
        self.discord_url = settings.DISCORD_WEBHOOK_URL
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = settings.TELEGRAM_CHAT_ID

    async def notify_deal_won(self, deal_data: Dict[str, Any], lead_data: Dict[str, Any]):
        """
        Broadcasts urgent high-priority celebration and action alert across Discord, Telegram & Email!
        """
        title = f"🎉 [DEAL WON] New Project Closed: ${deal_data.get('agreed_price', 0):.0f} USD!"
        body = (
            f"**Client:** {lead_data.get('contact_name')} ({lead_data.get('business_name')})\n"
            f"**Package:** {deal_data.get('package_name', '').replace('_', ' ').title()}\n"
            f"**Agreed Amount:** ${deal_data.get('agreed_price', 0):.0f} USD\n"
            f"**Client Email:** {lead_data.get('contact_email')}\n"
            f"**Payment Link Sent:** {deal_data.get('payment_link')}\n"
            f"**Status:** Order locked in! Ready for production kickoff."
        )

        logger.info(f"Broadcasting Won Deal notification: {title}")

        # 1. Discord Webhook
        if self.discord_url and self.discord_url.startswith("http"):
            try:
                payload = {
                    "username": "OmniLead Closer Bot",
                    "embeds": [{
                        "title": title,
                        "description": body,
                        "color": 0x22C55E,  # Vibrant Green
                        "fields": [
                            {"name": "Project Scope", "value": lead_data.get("audit_summary", "Turnkey web creation / automation")[:200]},
                            {"name": "Client Requirements", "value": deal_data.get("client_requirements", "Standard package specs")[:200]}
                        ],
                        "footer": {"text": f"{settings.BUSINESS_NAME} 24/7 Sales Engine"}
                    }]
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    await client.post(self.discord_url, json=payload)
            except Exception as e:
                logger.warning(f"Discord notification failed: {e}")

        # 2. Telegram Bot
        raw_tg_token = (self.telegram_token or settings.TELEGRAM_BOT_TOKEN or "").strip().replace(" ", "")
        if raw_tg_token.startswith("bot"):
            raw_tg_token = raw_tg_token[3:]
        raw_tg_chat = str(self.telegram_chat_id or settings.TELEGRAM_CHAT_ID or "").strip().replace(" ", "")

        if raw_tg_token and raw_tg_chat:
            try:
                tg_url = f"https://api.telegram.org/bot{raw_tg_token}/sendMessage"
                text = f"{title}\n\n{body}"
                async with httpx.AsyncClient(timeout=8.0) as client:
                    await client.post(tg_url, json={"chat_id": raw_tg_chat, "text": text, "parse_mode": "Markdown"})
            except Exception as e:
                logger.warning(f"Telegram notification failed: {e}")

        # 3. Notification to User's Business Email
        if settings.SMTP_USER and settings.SMTP_PASSWORD and settings.BUSINESS_EMAIL:
            try:
                msg = MIMEMultipart()
                msg["Subject"] = f"🚀 DEAL CLOSED: ${deal_data.get('agreed_price', 0):.0f} from {lead_data.get('business_name')}"
                msg["From"] = settings.SMTP_USER
                msg["To"] = settings.BUSINESS_EMAIL
                msg.attach(MIMEText(body, "plain"))

                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            except Exception as e:
                logger.warning(f"Email notification to business owner failed: {e}")

    async def send_test_telegram(self, token: str = None, chat_id: str = None) -> Dict[str, Any]:
        """Sends a verification ping to Telegram to confirm credentials."""
        raw_token = token or self.telegram_token or settings.TELEGRAM_BOT_TOKEN or ""
        raw_chat = chat_id or self.telegram_chat_id or settings.TELEGRAM_CHAT_ID or ""

        # Clean accidental spaces, newlines, or 'bot' prefixes
        bot_token = str(raw_token).strip().replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")
        if bot_token.startswith("bot"):
            bot_token = bot_token[3:]

        target_chat = str(raw_chat).strip().replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")

        if not bot_token or not target_chat:
            return {"success": False, "error": "Bot Token and Chat ID are required."}

        try:
            tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            msg = (
                "🤖 *OmniLead 24/7 Agent Connected!*\n\n"
                "✅ Telegram alerts are active.\n"
                "Whenever a client accepts a proposal or an order is locked in, you will be notified here immediately!"
            )
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(tg_url, json={"chat_id": target_chat, "text": msg, "parse_mode": "Markdown"})
                if resp.status_code == 200:
                    return {"success": True, "message": "Telegram ping sent successfully!"}
                
                try:
                    err_desc = resp.json().get("description", resp.text)
                except Exception:
                    err_desc = resp.text

                if resp.status_code == 404:
                    return {
                        "success": False,
                        "error": f"Invalid Bot Token (HTTP 404). Please re-copy the exact token from @BotFather without any spaces."
                    }
                elif "chat not found" in err_desc.lower() or resp.status_code == 400:
                    return {
                        "success": False,
                        "error": f"Telegram: '{err_desc}'. TIP: Have you opened your new bot in Telegram and clicked 'Start'?"
                    }
                else:
                    return {"success": False, "error": f"Telegram API error ({resp.status_code}): {err_desc}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
