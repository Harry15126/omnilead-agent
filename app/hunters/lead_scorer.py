import re
import json
import logging
import httpx
from typing import Dict, Any, Tuple
from app.config import settings, DEFAULT_PACKAGES

logger = logging.getLogger("omnilead.scorer")

class LeadScorer:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
        self.provider = settings.LLM_PROVIDER

    async def score_and_qualify(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates buyer intent score (0-100), selects best package,
        generates personalized pitch and rationale.
        """
        if settings.GEMINI_API_KEY:
            return await self._score_with_gemini(lead_data)
        elif settings.OPENAI_API_KEY:
            return await self._score_with_openai(lead_data)
        else:
            return self._heuristic_scoring(lead_data)

    def _heuristic_scoring(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        text = f"{lead.get('title', '')} {lead.get('raw_content', '')} {lead.get('audit_summary', '')}".lower()
        score = 65
        rationale = []

        # Package matching
        matched_pkg = "starter_landing_page"
        if any(w in text for w in ["automation", "bot", "auto-dm", "instagram", "schedule", "scraping"]):
            matched_pkg = "social_automation_suite"
            score += 15
            rationale.append("High demand for social media automation or custom bot integration.")
        elif any(w in text for w in ["full website", "complete redesign", "multi-page", "cms", "law", "clinic", "dental"]):
            matched_pkg = "full_business_website"
            score += 18
            rationale.append("Professional business requiring comprehensive multi-page web presence.")
        elif any(w in text for w in ["all-in-one", "grow", "scaling", "both website and social"]):
            matched_pkg = "growth_bundle"
            score += 25
            rationale.append("Expansive scope covering both web infrastructure and automated distribution.")
        else:
            score += 10
            rationale.append("Direct need for rapid conversion landing page or website fix.")

        # Intent signals
        if any(w in text for w in ["budget", "pay", "$", "urgent", "asap", "ready to start", "hiring"]):
            score += 15
            rationale.append("Explicit budget or urgent hiring signal detected.")

        # Local business without website bonus
        if lead.get("source") == "local_business" and not lead.get("has_website"):
            score += 20
            rationale.append("Verified commercial business operating with NO digital storefront.")

        score = min(98, max(40, score))
        package_info = DEFAULT_PACKAGES[matched_pkg]

        pitch = (
            f"Hi {lead.get('contact_name', 'there')},\n\n"
            f"I came across {lead.get('business_name', 'your business')} and noticed an immediate opportunity: "
            f"{lead.get('audit_summary', 'your online presence could generate significantly more customers with a modern digital storefront')}.\n\n"
            f"At {settings.BUSINESS_NAME}, we specialize in {package_info.name.lower()}s engineered specifically to turn visitors into paying clients. "
            f"Our turnaround is just {package_info.turnaround_days} days, complete with mobile-first design, SEO, and lead capture.\n\n"
            f"We can deliver this turnkey for {package_info.default_price:.0f} USD. "
            f"You can see our recent client work here: {settings.BUSINESS_WEBSITE}\n\n"
            f"Would you be open to a quick preview mockup this week?\n\n"
            f"Best regards,\n"
            f"{settings.AGENT_NAME}\n"
            f"{settings.BUSINESS_NAME} | {settings.BUSINESS_EMAIL}"
        )

        return {
            "score": score,
            "score_rationale": " • ".join(rationale),
            "recommended_package": matched_pkg,
            "target_price": package_info.default_price,
            "personalized_pitch": pitch,
        }

    async def _score_with_gemini(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            prompt = f"""
            You are a world-class autonomous B2B sales evaluator and deal closer for '{settings.BUSINESS_NAME}'.
            Our core packages:
            1. starter_landing_page: $499 (Min: $399) - High-converting single page, fast turnaround (3 days)
            2. full_business_website: $1200 (Min: $950) - Multi-page corporate/clinic/service website (7 days)
            3. social_automation_suite: $650 (Min: $500) - Automated DMs, social scheduler, lead capture bot
            4. growth_bundle: $1650 (Min: $1350) - Complete website + social media automation

            Evaluate this lead:
            Title: {lead.get('title')}
            Business Name: {lead.get('business_name')}
            Source: {lead.get('source')}
            Audit: {lead.get('audit_summary')}
            Raw content: {lead.get('raw_content')}

            Return ONLY a valid JSON object with the following keys:
            {{
                "score": <integer 0-100>,
                "score_rationale": "<concise explanation of buyer qualification>",
                "recommended_package": "<starter_landing_page|full_business_website|social_automation_suite|growth_bundle>",
                "target_price": <float>,
                "personalized_pitch": "<a compelling, professional, friendly cold pitch tailored to their situation>"
            }}
            """
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                if resp.status_code == 200:
                    text_content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    cleaned = re.sub(r"```json\s*", "", text_content)
                    cleaned = re.sub(r"```", "", cleaned).strip()
                    data = json.loads(cleaned)
                    return data
        except Exception as e:
            logger.warning(f"Gemini API qualification error: {e}. Falling back to heuristic scorer.")
        return self._heuristic_scoring(lead)

    async def _score_with_openai(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an autonomous sales lead scoring and pitching engine. Return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": f"Score and pitch this lead: {json.dumps(lead)}"
                    }
                ],
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
        except Exception as e:
            logger.warning(f"OpenAI API scoring error: {e}")
        return self._heuristic_scoring(lead)
