from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import Lead, Interaction, Deal, ActivityLog
from app.engines.ai_closer import AICloser
from app.engines.email_engine import EmailEngine
from app.config import settings

router = APIRouter(prefix="/api/leads", tags=["leads"])
closer = AICloser()
email_engine = EmailEngine()

class ManualLeadCreate(BaseModel):
    title: str
    business_name: str
    contact_name: str
    contact_email: str
    niche: Optional[str] = "Services"
    website_url: Optional[str] = None
    has_website: Optional[bool] = False
    audit_summary: Optional[str] = "Manual entry for targeted outreach"
    recommended_package: Optional[str] = "starter_landing_page"
    target_price: Optional[float] = 499.0

class SimulateReplyPayload(BaseModel):
    client_message: str

@router.get("")
async def list_leads(
    status: Optional[str] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Lead).order_by(desc(Lead.created_at))
    if status and status != "all":
        query = query.where(Lead.status == status)
    if source and source != "all":
        query = query.where(Lead.source == source)
    
    result = await db.execute(query)
    leads = result.scalars().all()
    return [l.to_dict() for l in leads]

@router.get("/{lead_id}")
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get interactions
    i_res = await db.execute(
        select(Interaction).where(Interaction.lead_id == lead_id).order_by(Interaction.created_at)
    )
    interactions = [i.to_dict() for i in i_res.scalars().all()]
    
    # Get deal if exists
    d_res = await db.execute(select(Deal).where(Deal.lead_id == lead_id))
    deal = d_res.scalar_one_or_none()
    
    lead_dict = lead.to_dict()
    lead_dict["interactions"] = interactions
    lead_dict["deal"] = deal.to_dict() if deal else None
    return lead_dict

@router.post("")
async def create_lead(payload: ManualLeadCreate, db: AsyncSession = Depends(get_db)):
    lead = Lead(
        source="manual",
        title=payload.title,
        business_name=payload.business_name,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        niche=payload.niche,
        website_url=payload.website_url,
        has_website=payload.has_website,
        audit_summary=payload.audit_summary,
        recommended_package=payload.recommended_package,
        target_price=payload.target_price,
        score=85,
        score_rationale="High-priority manual lead entered by owner.",
        status="discovered"
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead.to_dict()

@router.post("/{lead_id}/contact")
async def trigger_contact(lead_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    subject = f"Growth opportunity for {lead.business_name} - {settings.BUSINESS_NAME}"
    pitch_body = (
        f"Hi {lead.contact_name},\n\n"
        f"I was reviewing {lead.business_name} and noted: {lead.audit_summary}\n\n"
        f"At {settings.BUSINESS_NAME}, we help businesses turn traffic into booked clients with rapid-turnaround "
        f"modern web builds and automated social media workflows.\n\n"
        f"Our turnkey package is ${lead.target_price:.0f}. Would you like to review a quick wireframe preview?\n\n"
        f"Best regards,\n{settings.AGENT_NAME}\n{settings.BUSINESS_NAME} | {settings.BUSINESS_WEBSITE}"
    )

    email_engine.send_email(lead.contact_email, subject, pitch_body)
    lead.status = "contacted"

    interaction = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="email",
        subject=subject,
        message_body=pitch_body,
        ai_analysis="Manual outreach triggered from dashboard.",
        ai_strategy="Direct value proposition cold audit email.",
        proposed_price=lead.target_price
    )
    db.add(interaction)
    await db.commit()
    return {"status": "contacted", "lead": lead.to_dict()}

@router.post("/{lead_id}/simulate_reply")
async def simulate_reply(lead_id: int, payload: SimulateReplyPayload, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Inbound client interaction
    inbound_int = Interaction(
        lead_id=lead.id,
        direction="inbound",
        channel="simulator",
        subject="Re: Growth opportunity",
        message_body=payload.client_message
    )
    db.add(inbound_int)
    lead.status = "negotiating"
    await db.flush()

    # Get history
    h_res = await db.execute(
        select(Interaction).where(Interaction.lead_id == lead.id).order_by(Interaction.created_at)
    )
    history = [i.to_dict() for i in h_res.scalars().all()]

    # Run AI closer
    closer_res = await closer.handle_incoming_message(
        lead=lead.to_dict(),
        history=history,
        incoming_msg=payload.client_message,
        channel="simulator"
    )

    # Outbound AI interaction
    outbound_int = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="simulator",
        subject="Re: Growth opportunity",
        message_body=closer_res["reply_body"],
        ai_analysis=closer_res["ai_analysis"],
        ai_strategy=closer_res["ai_strategy"],
        proposed_price=closer_res["proposed_price"]
    )
    db.add(outbound_int)

    deal_created = False
    if closer_res["is_deal_closed"]:
        lead.status = "deal_won"
        d_info = closer_res["deal_info"]
        
        # Check if deal already exists
        d_check = await db.execute(select(Deal).where(Deal.lead_id == lead.id))
        existing_deal = d_check.scalar_one_or_none()
        if not existing_deal:
            deal = Deal(
                lead_id=lead.id,
                package_name=d_info["package_name"],
                agreed_price=d_info["agreed_price"],
                payment_link=d_info["payment_link"],
                client_requirements=d_info["client_requirements"],
                status="won_pending_payment"
            )
            db.add(deal)
            deal_created = True

    await db.commit()
    await db.refresh(lead)

    return {
        "status": "success",
        "lead": lead.to_dict(),
        "ai_response": closer_res["reply_body"],
        "ai_analysis": closer_res["ai_analysis"],
        "ai_strategy": closer_res["ai_strategy"],
        "proposed_price": closer_res["proposed_price"],
        "is_deal_closed": closer_res["is_deal_closed"]
    }
