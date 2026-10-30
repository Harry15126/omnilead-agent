from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models import Lead, Deal, ActivityLog

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("")
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Total counts
    total_leads_res = await db.execute(select(func.count(Lead.id)))
    total_leads = total_leads_res.scalar() or 0

    contacted_res = await db.execute(select(func.count(Lead.id)).where(Lead.status.in_(["contacted", "negotiating", "deal_won", "paid"])))
    total_contacted = contacted_res.scalar() or 0

    negotiating_res = await db.execute(select(func.count(Lead.id)).where(Lead.status == "negotiating"))
    total_negotiating = negotiating_res.scalar() or 0

    deals_res = await db.execute(select(func.count(Deal.id)))
    total_deals = deals_res.scalar() or 0

    revenue_res = await db.execute(select(func.sum(Deal.agreed_price)))
    total_revenue = revenue_res.scalar() or 0.0

    conversion_rate = (total_deals / total_contacted * 100) if total_contacted > 0 else 0.0

    return {
        "total_leads": total_leads,
        "total_contacted": total_contacted,
        "total_negotiating": total_negotiating,
        "total_deals": total_deals,
        "total_revenue": total_revenue,
        "conversion_rate": round(conversion_rate, 1),
    }

@router.get("/logs")
async def get_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(ActivityLog).order_by(desc(ActivityLog.created_at)).limit(limit))
    logs = res.scalars().all()
    return [l.to_dict() for l in logs]
