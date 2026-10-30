import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Lead, Interaction, Deal, ActivityLog
from app.hunters.reddit_hunter import RedditHunter
from app.hunters.local_business import LocalBusinessHunter
from app.hunters.social_hunter import SocialHunter
from app.hunters.lead_scorer import LeadScorer
from app.engines.email_engine import EmailEngine
from app.engines.ai_closer import AICloser
from app.engines.notifier import Notifier

logger = logging.getLogger("omnilead.scheduler")

class AutonomousScheduler:
    def __init__(self, broadcast_fn=None):
        self.scheduler = AsyncIOScheduler()
        self.broadcast_fn = broadcast_fn  # async function to push WebSocket updates
        self.reddit_hunter = RedditHunter()
        self.local_hunter = LocalBusinessHunter()
        self.social_hunter = SocialHunter()
        self.scorer = LeadScorer()
        self.email_engine = EmailEngine()
        self.closer = AICloser()
        self.notifier = Notifier()
        self.is_running = False

    async def log_activity(self, session, level: str, category: str, message: str, meta: str = None):
        log_entry = ActivityLog(level=level, category=category, message=message, meta_data=meta)
        session.add(log_entry)
        await session.commit()
        if self.broadcast_fn:
            await self.broadcast_fn({
                "type": "log",
                "data": log_entry.to_dict()
            })

    async def run_hunt_cycle(self):
        """Discovers, scores, and initiates contact for high-intent leads."""
        logger.info("Executing 24/7 lead hunting cycle across channels...")
        async with AsyncSessionLocal() as session:
            await self.log_activity(session, "INFO", "HUNTER", "Starting multi-channel lead discovery cycle (Reddit, Local Maps, Socials)...")
            
            raw_leads = []
            try:
                reddit_leads = await self.reddit_hunter.hunt()
                raw_leads.extend(reddit_leads)
            except Exception as e:
                logger.error(f"Reddit hunting error: {e}")

            try:
                local_leads = await self.local_hunter.hunt()
                raw_leads.extend(local_leads)
            except Exception as e:
                logger.error(f"Local business hunting error: {e}")

            try:
                social_leads = await self.social_hunter.hunt()
                raw_leads.extend(social_leads)
            except Exception as e:
                logger.error(f"Social hunting error: {e}")

            new_leads_count = 0
            contacted_count = 0

            for raw in raw_leads:
                # Check for existing lead by URL or email
                stmt = select(Lead).where(
                    (Lead.original_url == raw.get("original_url")) | 
                    (Lead.contact_email == raw.get("contact_email"))
                )
                res = await session.execute(stmt)
                existing = res.scalar_one_or_none()
                if existing:
                    continue

                # Score lead
                scored_data = await self.scorer.score_and_qualify(raw)
                
                lead = Lead(
                    source=raw.get("source", "reddit"),
                    title=raw.get("title", ""),
                    business_name=raw.get("business_name", ""),
                    niche=raw.get("niche", "General"),
                    contact_name=raw.get("contact_name", "Prospective Client"),
                    contact_email=raw.get("contact_email", ""),
                    contact_phone=raw.get("contact_phone"),
                    website_url=raw.get("website_url"),
                    has_website=raw.get("has_website", False),
                    audit_summary=raw.get("audit_summary"),
                    original_url=raw.get("original_url"),
                    score=scored_data.get("score", 50),
                    score_rationale=scored_data.get("score_rationale"),
                    recommended_package=scored_data.get("recommended_package", "starter_landing_page"),
                    target_price=scored_data.get("target_price", 499.0),
                    status="scored"
                )
                session.add(lead)
                await session.flush()
                new_leads_count += 1

                # Autonomous Outreach if score meets threshold
                if scored_data.get("score", 0) >= settings.MIN_LEAD_SCORE_TO_CONTACT:
                    pitch_body = scored_data.get("personalized_pitch", "")
                    subject = f"Growth opportunity for {lead.business_name} - {settings.BUSINESS_NAME}"
                    
                    if settings.AUTONOMOUS_MODE:
                        # Send email or simulated message
                        self.email_engine.send_email(lead.contact_email, subject, pitch_body)
                        lead.status = "contacted"
                        contacted_count += 1

                        # Record Interaction
                        interaction = Interaction(
                            lead_id=lead.id,
                            direction="outbound",
                            channel="email",
                            subject=subject,
                            message_body=pitch_body,
                            ai_analysis=f"Score: {lead.score}/100. High conversion probability.",
                            ai_strategy="Initial personalized audit pitch highlighting missing web presence and value proposition.",
                            proposed_price=lead.target_price
                        )
                        session.add(interaction)

                await session.commit()
                if self.broadcast_fn:
                    await self.broadcast_fn({"type": "lead_discovered", "data": lead.to_dict()})

            msg = f"Hunt cycle complete: {new_leads_count} new qualified leads found, {contacted_count} contacted."
            await self.log_activity(session, "SUCCESS", "HUNTER", msg)
            logger.info(msg)

    async def run_reply_check_cycle(self):
        """Checks for client replies, negotiates, and closes deals."""
        async with AsyncSessionLocal() as session:
            replies = self.email_engine.check_inbound_replies()
            if not replies:
                return

            for rep in replies:
                sender_email = rep.get("from_email", "")
                body = rep.get("body", "")

                # Find lead
                stmt = select(Lead).where(Lead.contact_email.like(f"%{sender_email}%"))
                res = await session.execute(stmt)
                lead = res.scalar_one_or_none()
                if not lead:
                    continue

                lead.status = "negotiating"

                # Record inbound interaction
                inbound_int = Interaction(
                    lead_id=lead.id,
                    direction="inbound",
                    channel="email",
                    subject=rep.get("subject", "Reply"),
                    message_body=body,
                )
                session.add(inbound_int)
                await session.flush()

                # Get conversation history
                h_stmt = select(Interaction).where(Interaction.lead_id == lead.id).order_by(Interaction.created_at)
                h_res = await session.execute(h_stmt)
                history = [i.to_dict() for i in h_res.scalars().all()]

                # Run Closer Brain
                closer_res = await self.closer.handle_incoming_message(
                    lead=lead.to_dict(),
                    history=history,
                    incoming_msg=body,
                    channel="email"
                )

                # Record AI reply
                outbound_int = Interaction(
                    lead_id=lead.id,
                    direction="outbound",
                    channel="email",
                    subject=f"Re: {rep.get('subject', 'Project Consultation')}",
                    message_body=closer_res["reply_body"],
                    ai_analysis=closer_res["ai_analysis"],
                    ai_strategy=closer_res["ai_strategy"],
                    proposed_price=closer_res["proposed_price"]
                )
                session.add(outbound_int)

                # If deal closed
                if closer_res["is_deal_closed"]:
                    lead.status = "deal_won"
                    d_info = closer_res["deal_info"]
                    deal = Deal(
                        lead_id=lead.id,
                        package_name=d_info["package_name"],
                        agreed_price=d_info["agreed_price"],
                        payment_link=d_info["payment_link"],
                        client_requirements=d_info["client_requirements"],
                        status="won_pending_payment"
                    )
                    session.add(deal)
                    await self.log_activity(
                        session, "SUCCESS", "CLOSER", 
                        f"🎉 Deal Won with {lead.contact_name} ({lead.business_name}) for ${d_info['agreed_price']:.0f}!"
                    )

                if settings.AUTONOMOUS_MODE:
                    self.email_engine.send_email(
                        to_email=lead.contact_email,
                        subject=f"Re: {rep.get('subject', 'Project Kickoff')}",
                        body=closer_res["reply_body"]
                    )

                await session.commit()
                if self.broadcast_fn:
                    await self.broadcast_fn({"type": "lead_updated", "data": lead.to_dict()})

    def start(self):
        if not self.is_running:
            self.scheduler.add_job(self.run_hunt_cycle, "interval", minutes=settings.SCAN_INTERVAL_MINUTES, id="hunt_cycle")
            self.scheduler.add_job(self.run_reply_check_cycle, "interval", minutes=settings.REPLY_CHECK_INTERVAL_MINUTES, id="reply_cycle")
            self.scheduler.start()
            self.is_running = True
            logger.info("Autonomous 24/7 background scheduler active.")

    def stop(self):
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped.")
