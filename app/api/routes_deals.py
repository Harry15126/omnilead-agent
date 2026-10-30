from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from app.database import get_db
from app.models import Deal, Lead, ActivityLog

router = APIRouter(prefix="/api/deals", tags=["deals"])

@router.get("")
async def list_deals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Deal).order_by(desc(Deal.created_at)))
    deals = result.scalars().all()
    
    out = []
    for d in deals:
        lead_res = await db.execute(select(Lead).where(Lead.id == d.lead_id))
        lead = lead_res.scalar_one_or_none()
        d_dict = d.to_dict()
        d_dict["lead"] = lead.to_dict() if lead else None
        out.append(d_dict)
    return out

@router.post("/{deal_id}/mark_paid")
async def mark_deal_paid(deal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    deal.payment_status = "paid"
    deal.status = "completed_paid"
    deal.closed_at = datetime.utcnow()

    # Update lead status
    lead_res = await db.execute(select(Lead).where(Lead.id == deal.lead_id))
    lead = lead_res.scalar_one_or_none()
    if lead:
        lead.status = "paid"

    log = ActivityLog(
        level="SUCCESS",
        category="PAYMENT",
        message=f"💰 Payment Verified: ${deal.agreed_price:.0f} collected for {deal.package_name}."
    )
    db.add(log)
    await db.commit()

    return {"status": "paid", "deal": deal.to_dict()}
