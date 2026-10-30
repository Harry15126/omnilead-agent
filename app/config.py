import os
from typing import List, Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class PricingPackage:
    def __init__(self, name: str, default_price: float, min_price: float, description: str, turnaround_days: int):
        self.name = name
        self.default_price = default_price
        self.min_price = min_price
        self.description = description
        self.turnaround_days = turnaround_days

    def to_dict(self):
        return {
            "name": self.name,
            "default_price": self.default_price,
            "min_price": self.min_price,
            "description": self.description,
            "turnaround_days": self.turnaround_days,
        }

class Settings(BaseSettings):
    # Agent Identity & Business
    AGENT_NAME: str = "OmniLead 24/7 Closer"
    BUSINESS_NAME: str = "Sehron Studios"
    BUSINESS_EMAIL: str = "contact@sehronstudios.com"
    BUSINESS_WEBSITE: str = "https://sehronstudios.com"
    BUSINESS_PHONE: str = ""
    SERVICES_OVERVIEW: str = (
        "High-converting modern website design, landing pages, custom AI workflows, "
        "and automated social media growth engines (Reels/Shorts pipelines & auto-DM)."
    )

    # Server Configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    SECRET_KEY: str = "omnilead-secret-key-change-in-production-2026"

    # Autonomous Guardrails
    AUTONOMOUS_MODE: bool = True  # True: auto sends messages & negotiates; False: queues for 1-click human approval
    MAX_DISCOUNT_PERCENT: float = 20.0  # Cannot negotiate lower than 20% off list price
    MIN_LEAD_SCORE_TO_CONTACT: int = 70  # Only reach out to leads scored >= 70
    SCAN_INTERVAL_MINUTES: int = 15
    REPLY_CHECK_INTERVAL_MINUTES: int = 5

    # LLM Provider (gemini, openai, or heuristic)
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.5-flash"

    # Business Email Integration (SMTP for sending, IMAP for reading replies)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USER: str = ""
    IMAP_PASSWORD: str = ""

    # Payment Integrations
    STRIPE_API_KEY: str = ""
    STRIPE_PAYMENT_LINK_BASE: str = "https://buy.stripe.com/test_omnilead"
    PAYPAL_ME_LINK: str = "https://paypal.me/vitalix"

    # Notifications
    DISCORD_WEBHOOK_URL: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Lead Hunter Target Niches & Keywords
    TARGET_NICHES: List[str] = [
        "Dentists & Orthodontists",
        "HVAC & Plumbing Contractors",
        "Law Firms & Attorneys",
        "Restaurants & Cafes",
        "Fitness Studios & Personal Trainers",
        "E-commerce Brands",
        "Real Estate Agencies",
    ]
    
    REDDIT_SUBREDDITS: List[str] = [
        "forhire",
        "freelance_forhire",
        "webdev",
        "smallbusiness",
        "entrepreneur",
        "startups",
    ]

    REDDIT_KEYWORDS: List[str] = [
        "need website",
        "looking for web developer",
        "build landing page",
        "redesign website",
        "social media automation",
        "need a bot",
        "looking to hire designer",
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Standard Service Catalog (No Artificial Price Floor - Maximum Deal Conversion)
DEFAULT_PACKAGES = {
    "starter_landing_page": PricingPackage(
        name="High-Converting Landing Page",
        default_price=499.0,
        min_price=0.0,
        description="Custom responsive landing page designed for conversion, SEO-optimized, mobile-first, with lead capture forms and 30-day warranty.",
        turnaround_days=3,
    ),
    "full_business_website": PricingPackage(
        name="Complete Modern Business Website",
        default_price=1200.0,
        min_price=0.0,
        description="Multi-page professional website (5-8 pages), CMS integration, fast loading speeds, interactive animations, SEO, and analytics setup.",
        turnaround_days=7,
    ),
    "social_automation_suite": PricingPackage(
        name="Social Media Automation Engine",
        default_price=650.0,
        min_price=0.0,
        description="Automated posting pipeline, intelligent DM responder bot, auto-scheduling across Instagram/X/LinkedIn, and monthly analytics reporting.",
        turnaround_days=4,
    ),
    "growth_bundle": PricingPackage(
        name="All-In-One Digital Growth Bundle",
        default_price=1650.0,
        min_price=0.0,
        description="Full business website + Social media automation engine + 3 months priority technical support and performance audits.",
        turnaround_days=10,
    ),
}
