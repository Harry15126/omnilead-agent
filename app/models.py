from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), default="reddit")  # reddit, local_business, social, manual
    title = Column(String(255), nullable=True)
    business_name = Column(String(255), nullable=True)
    niche = Column(String(100), nullable=True)
    contact_name = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    website_url = Column(String(500), nullable=True)
    has_website = Column(Boolean, default=False)
    audit_summary = Column(Text, nullable=True)
    original_url = Column(String(500), nullable=True)
    
    score = Column(Integer, default=50)  # 0 to 100
    score_rationale = Column(Text, nullable=True)
    recommended_package = Column(String(100), default="starter_landing_page")
    target_price = Column(Float, default=499.0)
    
    status = Column(String(50), default="discovered")  
    # discovered -> scored -> contacted -> negotiating -> deal_won -> paid -> rejected

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interactions = relationship("Interaction", back_populates="lead", cascade="all, delete-orphan")
    deal = relationship("Deal", back_populates="lead", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "business_name": self.business_name,
            "niche": self.niche,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "website_url": self.website_url,
            "has_website": self.has_website,
            "audit_summary": self.audit_summary,
            "original_url": self.original_url,
            "score": self.score,
            "score_rationale": self.score_rationale,
            "recommended_package": self.recommended_package,
            "target_price": self.target_price,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    direction = Column(String(20), default="outbound")  # outbound, inbound
    channel = Column(String(50), default="email")       # email, reddit_dm, x_dm, simulator
    subject = Column(String(255), nullable=True)
    message_body = Column(Text, nullable=False)
    ai_analysis = Column(Text, nullable=True)
    ai_strategy = Column(Text, nullable=True)
    proposed_price = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="interactions")

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "direction": self.direction,
            "channel": self.channel,
            "subject": self.subject,
            "message_body": self.message_body,
            "ai_analysis": self.ai_analysis,
            "ai_strategy": self.ai_strategy,
            "proposed_price": self.proposed_price,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, unique=True)
    package_name = Column(String(100), nullable=False)
    agreed_price = Column(Float, nullable=False)
    payment_method = Column(String(50), default="stripe")
    payment_link = Column(String(500), nullable=True)
    payment_status = Column(String(50), default="pending")  # pending, paid, cancelled
    stripe_session_id = Column(String(255), nullable=True)
    client_requirements = Column(Text, nullable=True)
    deadline_days = Column(Integer, default=7)
    status = Column(String(50), default="won_pending_payment")  # won_pending_payment, completed_paid
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    lead = relationship("Lead", back_populates="deal")

    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "package_name": self.package_name,
            "agreed_price": self.agreed_price,
            "payment_method": self.payment_method,
            "payment_link": self.payment_link,
            "payment_status": self.payment_status,
            "stripe_session_id": self.stripe_session_id,
            "client_requirements": self.client_requirements,
            "deadline_days": self.deadline_days,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), default="INFO")  # INFO, SUCCESS, WARNING, ERROR
    category = Column(String(50), default="SYSTEM")  # HUNTER, CLOSER, SCHEDULER, PAYMENT, NOTIFIER
    message = Column(Text, nullable=False)
    meta_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "meta_data": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
