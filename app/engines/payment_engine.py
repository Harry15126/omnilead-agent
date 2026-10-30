import logging
import uuid
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("omnilead.payment")

class PaymentEngine:
    def __init__(self):
        self.stripe_key = settings.STRIPE_API_KEY
        self.paypal_link = settings.PAYPAL_ME_LINK

    def generate_payment_link(self, lead_id: int, package_name: str, amount: float, client_email: str) -> Dict[str, Any]:
        """
        Creates a direct, secure payment link for the client to complete checkout.
        Integrates with Stripe Checkout API or pre-formatted invoice/PayPal checkout.
        """
        invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        
        # If Stripe API Key is set, create a real Stripe Checkout Session
        if self.stripe_key and self.stripe_key.startswith("sk_"):
            try:
                import stripe  # type: ignore
                stripe.api_key = self.stripe_key
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"{package_name.replace('_', ' ').title()} - {settings.BUSINESS_NAME}",
                                "description": f"Custom project kickoff for {client_email}",
                            },
                            "unit_amount": int(amount * 100),
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    customer_email=client_email,
                    success_url=f"{settings.BUSINESS_WEBSITE}/success?session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{settings.BUSINESS_WEBSITE}/cancelled",
                    metadata={"lead_id": str(lead_id), "invoice_id": invoice_id}
                )
                return {
                    "invoice_id": invoice_id,
                    "payment_url": session.url,
                    "session_id": session.id,
                    "method": "stripe_checkout",
                    "amount": amount
                }
            except Exception as e:
                logger.warning(f"Stripe session creation error: {e}. Falling back to hosted link.")

        # 1. Prioritize PayPal if configured (always read dynamically from current settings)
        paypal_link = settings.PAYPAL_ME_LINK or self.paypal_link
        if paypal_link and ("paypal.me" in paypal_link.lower() or not paypal_link.startswith("http")):
            clean_paypal = paypal_link.strip().rstrip("/")
            if not clean_paypal.startswith("http"):
                clean_paypal = f"https://paypal.me/{clean_paypal.replace('@', '')}"
            payment_url = f"{clean_paypal}/{int(amount)}USD"
            return {
                "invoice_id": invoice_id,
                "payment_url": payment_url,
                "session_id": invoice_id,
                "method": "paypal",
                "amount": amount
            }

        # 2. Standard Stripe checkout link fallback
        if settings.STRIPE_PAYMENT_LINK_BASE and not "test_omnilead" in settings.STRIPE_PAYMENT_LINK_BASE:
            payment_url = f"{settings.STRIPE_PAYMENT_LINK_BASE}?prefilled_email={client_email}&amount={int(amount)}&client_ref={invoice_id}"
        elif paypal_link:
            clean_paypal = paypal_link.strip().rstrip("/")
            payment_url = f"{clean_paypal}/{int(amount)}USD"
        else:
            payment_url = f"https://paypal.me/yourname/{int(amount)}USD"

        return {
            "invoice_id": invoice_id,
            "payment_url": payment_url,
            "session_id": invoice_id,
            "method": "hosted_checkout",
            "amount": amount
        }
