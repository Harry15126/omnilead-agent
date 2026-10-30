import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger("omnilead.email")

class EmailEngine:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD

        self.imap_host = settings.IMAP_HOST
        self.imap_port = settings.IMAP_PORT
        self.imap_user = settings.IMAP_USER or settings.SMTP_USER
        self.imap_password = settings.IMAP_PASSWORD or settings.SMTP_PASSWORD

    def send_email(self, to_email: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Sends outbound email via SMTP.
        If SMTP credentials are not yet entered, records as queued/simulated.
        """
        if not self.smtp_user or not self.smtp_password:
            logger.info(f"[SIMULATED OUTBOUND EMAIL] To: {to_email} | Subject: {subject}")
            return {
                "status": "simulated",
                "message": "Sent in local simulation mode (Configure SMTP in settings for live delivery)",
                "to": to_email,
                "subject": subject
            }

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.BUSINESS_NAME} <{self.smtp_user}>"
            msg["To"] = to_email
            msg["Reply-To"] = settings.BUSINESS_EMAIL

            # Plain text part
            text_part = MIMEText(body, "plain")
            msg.attach(text_part)

            # HTML formatted part
            html_content = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                {body.replace(chr(10), '<br>')}
                <br><br>
                <hr style="border: none; border-top: 1px solid #eee;">
                <p style="font-size: 12px; color: #777;">
                    <strong>{settings.BUSINESS_NAME}</strong> &bull; {settings.BUSINESS_WEBSITE}<br>
                    {settings.SERVICES_OVERVIEW}
                </p>
            </div>
            """
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            if int(self.smtp_port) == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, int(self.smtp_port), timeout=12.0)
            else:
                server = smtplib.SMTP(self.smtp_host, int(self.smtp_port), timeout=12.0)
                server.starttls()

            with server:
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Live email dispatched successfully to {to_email}")
            return {"status": "sent", "to": to_email, "subject": subject}
        except Exception as e:
            logger.error(f"Failed to dispatch live email to {to_email}: {e}")
            return {"status": "error", "error": str(e), "to": to_email}

    def test_connection(self, host: str, port: int, user: str, password: str, to_email: str = None) -> Dict[str, Any]:
        """Tests SMTP credentials and optionally sends a verification email."""
        clean_host = host.strip()
        clean_user = user.strip()
        clean_pwd = password.strip()
        target_to = (to_email or user).strip()

        try:
            if int(port) == 465:
                server = smtplib.SMTP_SSL(clean_host, int(port), timeout=10.0)
            else:
                server = smtplib.SMTP(clean_host, int(port), timeout=10.0)
                server.starttls()

            with server:
                server.login(clean_user, clean_pwd)

                # Send test email
                msg = MIMEMultipart()
                msg["Subject"] = "✅ OmniLead Business Email Connected Successfully!"
                msg["From"] = f"{settings.BUSINESS_NAME} <{clean_user}>"
                msg["To"] = target_to
                msg.attach(MIMEText(
                    f"Hello!\n\nYour Zoho business email ({clean_user}) is now successfully connected to OmniLead 24/7 Agent.\n"
                    f"Your agent is authorized to send personalized outreach and receive client responses.\n\n"
                    f"OmniLead System Status: ACTIVE", "plain"
                ))
                server.send_message(msg)

            return {"success": True, "message": f"Verification email successfully sent to {target_to}!"}
        except smtplib.SMTPAuthenticationError as e:
            return {"success": False, "error": f"Authentication failed: Invalid email or Zoho App Password ({e.smtp_error.decode(errors='ignore') if hasattr(e, 'smtp_error') else str(e)})."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_inbound_replies(self) -> List[Dict[str, Any]]:
        """
        Polls IMAP inbox for new unread client replies.
        """
        if not self.imap_user or not self.imap_password:
            return []

        replies = []
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.imap_user, self.imap_password)
            mail.select("inbox")

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK" or not messages[0]:
                mail.logout()
                return []

            for num in messages[0].split():
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                sender = msg.get("From", "")
                subject = msg.get("Subject", "")

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                replies.append({
                    "from_email": sender,
                    "subject": subject,
                    "body": body.strip(),
                    "raw_msg_id": num.decode()
                })

            mail.logout()
        except Exception as e:
            logger.warning(f"IMAP check error: {e}")

        return replies
