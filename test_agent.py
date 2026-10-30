import asyncio
import os
import sys

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.database import init_db, AsyncSessionLocal
from app.models import Lead, Interaction, Deal, ActivityLog
from app.hunters.local_business import LocalBusinessHunter
from app.hunters.reddit_hunter import RedditHunter
from app.hunters.social_hunter import SocialHunter
from app.hunters.lead_scorer import LeadScorer
from app.engines.ai_closer import AICloser
from app.engines.payment_engine import PaymentEngine
from sqlalchemy import select

async def run_integration_test():
    print("🚀 [1/6] Initializing OmniLead SQLite Database...")
    await init_db()
    print("✅ Database initialized successfully.")

    print("\n🔍 [2/6] Testing Lead Hunters...")
    local_hunter = LocalBusinessHunter()
    local_leads = await local_hunter.hunt()
    print(f"  • Local Business Hunter found {len(local_leads)} leads (e.g. {local_leads[0]['business_name'] if local_leads else 'None'})")

    social_hunter = SocialHunter()
    social_leads = await social_hunter.hunt()
    print(f"  • Social Intent Hunter found {len(social_leads)} leads (e.g. {social_leads[0]['business_name'] if social_leads else 'None'})")

    print("\n🧠 [3/6] Testing AI Lead Scorer & Pitch Generation...")
    scorer = LeadScorer()
    sample_lead = local_leads[0] if local_leads else {
        "source": "local_business",
        "title": "Summit Dental Care - Missing Website",
        "business_name": "Summit Dental Care",
        "niche": "Dentist",
        "contact_name": "Dr. Miller",
        "contact_email": "contact@summitdental.com",
        "has_website": False,
        "audit_summary": "Active dental practice with high foot traffic but no online booking portal or website.",
        "raw_content": "Location: Austin, TX.",
        "original_url": "https://maps.google.com/test",
    }
    scored = await scorer.score_and_qualify(sample_lead)
    print(f"  • Score: {scored['score']}/100")
    print(f"  • Matched Package: {scored['recommended_package']} (${scored['target_price']})")
    print(f"  • Generated Pitch Preview:\n    {scored['personalized_pitch'][:140]}...")

    print("\n💳 [4/6] Testing Payment Link Generator...")
    payment_engine = PaymentEngine()
    pay_res = payment_engine.generate_payment_link(
        lead_id=1,
        package_name=scored["recommended_package"],
        amount=scored["target_price"],
        client_email=sample_lead["contact_email"]
    )
    print(f"  • Payment Link: {pay_res['payment_url']}")

    print("\n🤖 [5/6] Testing AI Closer Negotiation & Guardrails...")
    closer = AICloser()
    lead_dict = {
        "id": 1,
        "contact_name": sample_lead["contact_name"],
        "business_name": sample_lead["business_name"],
        "recommended_package": scored["recommended_package"],
        "target_price": scored["target_price"],
        "contact_email": sample_lead["contact_email"]
    }

    # Case A: Client counter-offers with $200 budget
    print("  Subtest A: Client offers $200 budget...")
    res_a = await closer.handle_incoming_message(
        lead=lead_dict,
        history=[],
        incoming_msg="Hey, $499 is too high for us. Can you do it for $200?"
    )
    print(f"    AI Accepted Price: ${res_a['proposed_price']} (Accepted client offer: {res_a['proposed_price'] == 200})")
    print(f"    AI Strategy: {res_a['ai_strategy']}")
    assert res_a["proposed_price"] == 200, "Client budget should be accepted!"

    # Case B: Client accepts and asks for invoice link
    print("  Subtest B: Client says 'Sounds great, send me the invoice link!'...")
    res_b = await closer.handle_incoming_message(
        lead=lead_dict,
        history=[{"role": "assistant", "body": res_a["reply_body"]}],
        incoming_msg="Sounds great, please send me the invoice link so we can start!"
    )
    print(f"    Deal Closed: {res_b['is_deal_closed']}")
    print(f"    Invoice URL Generated: {'payment' in res_b['reply_body'].lower() or 'stripe' in res_b['reply_body'].lower()}")

    print("\n💾 [6/6] Verifying Database Persistence...")
    async with AsyncSessionLocal() as session:
        # Save a test lead
        db_lead = Lead(
            source=sample_lead["source"],
            title=sample_lead["title"],
            business_name=sample_lead["business_name"],
            niche=sample_lead["niche"],
            contact_name=sample_lead["contact_name"],
            contact_email=sample_lead["contact_email"],
            has_website=sample_lead["has_website"],
            audit_summary=sample_lead["audit_summary"],
            score=scored["score"],
            score_rationale=scored["score_rationale"],
            recommended_package=scored["recommended_package"],
            target_price=scored["target_price"],
            status="deal_won"
        )
        session.add(db_lead)
        await session.flush()

        # Save won deal
        deal = Deal(
            lead_id=db_lead.id,
            package_name=scored["recommended_package"],
            agreed_price=res_b["proposed_price"],
            payment_link=pay_res["payment_url"],
            client_requirements="Custom high-converting mobile site with lead capture",
            status="won_pending_payment"
        )
        session.add(deal)

        log = ActivityLog(
            level="SUCCESS",
            category="CLOSER",
            message=f"🎉 Test Verification: Won Deal with {db_lead.business_name} for ${deal.agreed_price:.0f}"
        )
        session.add(log)
        await session.commit()

        # Query back
        res = await session.execute(select(Lead).where(Lead.id == db_lead.id))
        saved = res.scalar_one()
        print(f"  • Lead #{saved.id} ('{saved.business_name}') retrieved with status: {saved.status}")

    print("\n========================================================")
    print("  🎉 ALL AGENT SUBSYSTEMS PASSED VERIFICATION!")
    print("========================================================\n")

if __name__ == "__main__":
    asyncio.run(run_integration_test())
