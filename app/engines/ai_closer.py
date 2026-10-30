import re
import json
import logging
import httpx
from typing import Dict, Any, List, Tuple
from app.config import settings, DEFAULT_PACKAGES
from app.engines.payment_engine import PaymentEngine
from app.engines.notifier import Notifier

logger = logging.getLogger("omnilead.closer")

class AICloser:
    def __init__(self):
        self.payment_engine = PaymentEngine()
        self.notifier = Notifier()

    async def handle_incoming_message(
        self,
        lead: Dict[str, Any],
        history: List[Dict[str, Any]],
        incoming_msg: str,
        channel: str = "email"
    ) -> Dict[str, Any]:
        """
        Processes client response, applies pricing guardrails, negotiates,
        handles objections, and closes deal when client expresses readiness.
        """
        pkg_key = lead.get("recommended_package", "starter_landing_page")
        pkg_info = DEFAULT_PACKAGES.get(pkg_key, DEFAULT_PACKAGES["starter_landing_page"])

        current_quote = lead.get("target_price", pkg_info.default_price)
        min_allowed = pkg_info.min_price

        # Check if client is ready to buy / asking for payment
        is_closing_intent = self._detect_closing_intent(incoming_msg)
        is_price_objection, offered_price = self._detect_price_objection(incoming_msg)

        if settings.GEMINI_API_KEY:
            ai_result = await self._generate_gemini_reply(lead, history, incoming_msg, pkg_info, min_allowed)
        elif settings.OPENAI_API_KEY:
            ai_result = await self._generate_openai_reply(lead, history, incoming_msg, pkg_info, min_allowed)
        else:
            ai_result = self._rule_based_negotiation(lead, incoming_msg, pkg_info, min_allowed, is_closing_intent, is_price_objection, offered_price)

        final_price = ai_result.get("proposed_price", current_quote)
        if final_price < 1.0:
            final_price = current_quote

        deal_created = False
        deal_info = None

        if ai_result.get("is_deal_closed") or is_closing_intent:
            payment_data = self.payment_engine.generate_payment_link(
                lead_id=lead.get("id", 1),
                package_name=pkg_info.name,
                amount=final_price,
                client_email=lead.get("contact_email", "client@domain.com")
            )
            ai_result["reply_body"] += f"\n\n👉 Secure Kickoff & Invoice Link: {payment_data['payment_url']}\nOnce completed, our technical kickoff begins immediately and you will receive your project onboarding questionnaire."
            
            deal_info = {
                "package_name": pkg_info.name,
                "agreed_price": final_price,
                "payment_link": payment_data["payment_url"],
                "payment_status": "pending",
                "client_requirements": f"Negotiated package: {pkg_info.name}. Client request: {incoming_msg[:200]}",
                "status": "won_pending_payment"
            }
            deal_created = True

            # Trigger immediate notification to the owner
            await self.notifier.notify_deal_won(deal_info, lead)

        return {
            "reply_body": ai_result["reply_body"],
            "ai_analysis": ai_result["ai_analysis"],
            "ai_strategy": ai_result["ai_strategy"],
            "proposed_price": final_price,
            "is_deal_closed": deal_created,
            "deal_info": deal_info
        }

    def _detect_closing_intent(self, text: str) -> bool:
        t = text.lower()
        signals = [
            "invoice", "payment", "payment link", "send link", "send me the link",
            "invoice link", "let's do it", "sounds good", "ready to move forward",
            "how do we pay", "let's start", "i'm interested", "what's next",
            "contract", "sign me up", "deal", "let's proceed", "start project",
            "send details", "kickoff", "where do i pay"
        ]
        return any(s in t for s in signals)

    def _detect_price_objection(self, text: str) -> Tuple[bool, float]:
        t = text.lower()
        price_signals = ["expensive", "too much", "budget", "can you do", "discount", "cheaper", "lower", "afford", "less"]
        is_obj = any(s in t for s in price_signals)

        # Look specifically for patterns like 'can you do $200', 'budget is 300', 'for $250'
        specific_match = re.search(r"(?:do|for|budget\s*(?:is|of)?|afford|pay|at)\s*\$?(\d+)", t)
        if specific_match:
            offered = float(specific_match.group(1))
            return True, offered

        # Fallback: extract all numbers and pick the lowest or last mentioned
        all_matches = re.findall(r"\$(\d+)|(\d+)\s*(?:dollars|usd|bucks)", t)
        if all_matches:
            nums = [float(a or b) for a, b in all_matches if a or b]
            if nums:
                offered = min(nums) if is_obj else nums[-1]
                return is_obj, offered

        return is_obj, 0.0

    def _rule_based_negotiation(
        self,
        lead: Dict[str, Any],
        msg: str,
        pkg: Any,
        min_price: float,
        is_closing: bool,
        is_price_obj: bool,
        offered: float
    ) -> Dict[str, Any]:
        contact = lead.get("contact_name", "there")
        business = lead.get("business_name", "your business")

        if is_closing:
            return {
                "reply_body": (
                    f"Hi {contact},\n\n"
                    f"Fantastic! We're excited to partner with {business} and deliver a high-converting {pkg.name.lower()}.\n\n"
                    f"I have finalized your agreement at ${pkg.default_price:.0f} USD with an estimated turnaround of {pkg.turnaround_days} business days."
                ),
                "ai_analysis": "Client expressed clear buying intent and requested payment/kickoff.",
                "ai_strategy": "Generate instant payment link, summarize scope, lock in timeline, and confirm order.",
                "proposed_price": pkg.default_price,
                "is_deal_closed": True
            }

        if is_price_obj:
            if offered > 0:
                agreed = offered
                strategy = f"Client offered their target budget of ${offered:.0f}. Since we build everything in-house with zero fulfillment cost, accepted their exact budget to lock in the paying order!"
                reply = (
                    f"Hi {contact},\n\n"
                    f"Thanks for being upfront about your budget! Because I engineer and build everything directly in-house without agency overhead, "
                    f"I would be glad to do this for ${agreed:.0f} USD for you.\n\n"
                    f"This still includes all core deliverables: custom design, full mobile responsiveness, speed optimization, and lead capture.\n\n"
                    f"Shall I send over the kickoff invoice link so we can begin this week?"
                )
            else:
                agreed = round(pkg.default_price * 0.6)  # Give a 40% discount if they ask for cheaper without a number
                strategy = f"Client requested a budget discount without naming amount. Offered an attractive builder rate of ${agreed:.0f} to lock in the deal."
                reply = (
                    f"Hi {contact},\n\n"
                    f"I completely understand wanting to keep costs efficient. Because I build and deliver everything directly in-house, "
                    f"I can approve a special builder discount of ${agreed:.0f} USD for the complete project (down from ${pkg.default_price:.0f}).\n\n"
                    f"This still includes all deliverables, mobile speed optimization, and full support.\n\n"
                    f"Would ${agreed:.0f} work for your budget?"
                )
            return {
                "reply_body": reply,
                "ai_analysis": "Client raised budget/pricing objection.",
                "ai_strategy": strategy,
                "proposed_price": agreed,
                "is_deal_closed": False
            }

        # Questions about timeline, proof, or technology
        t = msg.lower()
        if any(w in t for w in ["timeline", "how long", "when", "days"]):
            return {
                "reply_body": (
                    f"Hi {contact},\n\n"
                    f"Our guaranteed turnaround for the {pkg.name} is {pkg.turnaround_days} business days from kickoff.\n"
                    f"You'll get an initial live staging preview within 48 hours for your feedback.\n\n"
                    f"Would you like us to reserve a production slot for this week?"
                ),
                "ai_analysis": "Client inquiring about timeline and delivery speed.",
                "ai_strategy": "Reassure with rapid timeline (turnaround days) and prompt to reserve production slot.",
                "proposed_price": pkg.default_price,
                "is_deal_closed": False
            }

        if any(w in t for w in ["examples", "portfolio", "past work", "previous", "show me"]):
            return {
                "reply_body": (
                    f"Hi {contact},\n\n"
                    f"You can explore our live portfolio and case studies directly on our website: {settings.BUSINESS_WEBSITE}\n\n"
                    f"For {business}, we would tailor the layout specifically to your niche, focusing on customer acquisition and clean mobile speed.\n\n"
                    f"If you'd like, I can prepare a custom wireframe preview for you. Let me know!"
                ),
                "ai_analysis": "Client requesting social proof / portfolio.",
                "ai_strategy": "Direct to business website, offer custom wireframe, and steer toward next step.",
                "proposed_price": pkg.default_price,
                "is_deal_closed": False
            }

        # General welcoming inquiry
        return {
            "reply_body": (
                f"Hi {contact},\n\n"
                f"Thanks for following up! For {business}, our {pkg.name} will handle everything turnkey: "
                f"high-converting modern layout, full mobile responsiveness, SEO foundations, and automated lead capture.\n\n"
                f"Our standard investment is ${pkg.default_price:.0f} with a {pkg.turnaround_days}-day delivery.\n\n"
                f"Would you like me to send the kickoff details, or do you have any specific feature requirements you'd like included?"
            ),
            "ai_analysis": "General positive inquiry from prospect.",
            "ai_strategy": "Affirm scope, reiterate turnaround & price, and propose kickoff.",
            "proposed_price": pkg.default_price,
            "is_deal_closed": False
        }

    async def _generate_gemini_reply(self, lead: Dict, history: List, msg: str, pkg: Any, min_price: float) -> Dict:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            prompt = f"""
            You are '{settings.AGENT_NAME}', the master autonomous deal closer for '{settings.BUSINESS_NAME}'.
            Website: {settings.BUSINESS_WEBSITE} | Email: {settings.BUSINESS_EMAIL}

            CLIENT LEAD:
            Name: {lead.get('contact_name')}
            Business: {lead.get('business_name')}
            Recommended Package: {pkg.name} (List Price: ${pkg.default_price}, Minimum Floor: ${min_price})
            Turnaround: {pkg.turnaround_days} days

            HISTORY:
            {json.dumps(history[-4:] if history else [])}

            LATEST CLIENT MESSAGE:
            "{msg}"

            CRITICAL RULES:
            1. We build everything directly in-house, so our fulfillment cost is zero. Always prioritize CLOSING the deal! If client offers any budget (e.g. $80, $150, $200, $250, $300), ACCEPT IT enthusiastically to win the paying order.
            2. If client says "yes", "deal", "send invoice/link", "let's start", mark "is_deal_closed": true.
            3. Always maintain an ultra-professional, reassuring, consultative tone.
            4. Keep responses concise (under 120 words).

            Return valid JSON only:
            {{
                "reply_body": "<email body response>",
                "ai_analysis": "<1-sentence breakdown of client stance>",
                "ai_strategy": "<1-sentence reason for chosen negotiation tactic>",
                "proposed_price": <number>,
                "is_deal_closed": <boolean>
            }}
            """
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                if resp.status_code == 200:
                    text_content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    cleaned = re.sub(r"```json\s*", "", text_content)
                    cleaned = re.sub(r"```", "", cleaned).strip()
                    return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Gemini closer error: {e}")
        return self._rule_based_negotiation(lead, msg, pkg, min_price, self._detect_closing_intent(msg), False, 0)

    async def _generate_openai_reply(self, lead: Dict, history: List, msg: str, pkg: Any, min_price: float) -> Dict:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an autonomous sales negotiator and deal closer. Follow pricing bounds strictly. Return JSON only."},
                    {"role": "user", "content": f"Negotiate with client. Package: {pkg.name}, List: ${pkg.default_price}, Min: ${min_price}. Message: {msg}"}
                ],
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    return json.loads(resp.json()["choices"][0]["message"]["content"])
        except Exception as e:
            logger.warning(f"OpenAI closer error: {e}")
        return self._rule_based_negotiation(lead, msg, pkg, min_price, self._detect_closing_intent(msg), False, 0)
