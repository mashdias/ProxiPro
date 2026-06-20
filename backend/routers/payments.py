import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from bson import ObjectId
from database import users_collection, settings_collection
from dependencies import get_current_user
from datetime import datetime, timezone

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_123")

@router.post("/create-checkout-session")
async def create_checkout_session(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can upgrade to premium")

    try:
        settings = await settings_collection.find_one({"_id": "global_settings"})
        if settings:
            vendor_fee = settings.get("vendorPremiumFee", 2000)
        else:
            vendor_fee = 2000

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'lkr',
                    'product_data': {
                        'name': 'ProxiPro Premium Upgrade',
                    },
                    'unit_amount': int(vendor_fee * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='http://localhost:3000/dashboard?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='http://localhost:3000/dashboard?canceled=true',
            client_reference_id=str(current_user.get("_id", current_user.get("user_id")))
        )
        return {"url": session.url}
    except Exception as e:
        print(f"Stripe Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/verify-session")
async def verify_session(session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            vendor_id = session.client_reference_id
            if vendor_id:
                result = await users_collection.update_one(
                    {"_id": ObjectId(vendor_id)},
                    {"$set": {
                        "vendorProfile.isPremium": True,
                        "vendorProfile.paymentStatus": "Paid via Stripe",
                        "vendorProfile.premiumPaymentDate": datetime.now(timezone.utc).isoformat()
                    }}
                )
                if result.matched_count > 0:
                    return {"message": "Payment successful and vendor upgraded"}
                
        return {"message": "Payment not verified or vendor not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
