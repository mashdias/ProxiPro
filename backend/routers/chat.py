import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from google import genai

router = APIRouter()

SYSTEM_INSTRUCTION = """You are ProxiBot, the official AI assistant for ProxiPro, a Sri Lankan local service marketplace. Always be friendly, concise, and reply in the user's language (English or Singlish/Sinhala). 

STRICT BUSINESS RULES YOU MUST FOLLOW:
1. **For Customers (Free vs. Premium):** Anyone can browse services and register for free. However, to get EXCLUSIVE DISCOUNTS from vendors, customers MUST pay for a 'ProxiPro VIP/Premium Membership'. Do not say discounts are completely free. 
2. **Contacting Vendors:** Unregistered users cannot see full vendor contact details. They must register and log in to view phone numbers or send messages.
3. **For Vendors:** Vendors must register and pay a platform fee/subscription to fully list their services, connect with customers, and get the 'Verified Vendor' badge.
4. **General:** If asked how to do something, guide them step-by-step. If asked about payments, clearly explain the Vendor fee or the Customer VIP membership."""

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = []

@router.post("")
async def chat_with_bot(request: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Gemini API Key is not configured")

    try:
        client = genai.Client(api_key=api_key)
        
        # Format history to match the new SDK requirements
        contents = []
        for msg in request.history:
            role = msg.get("role", "user")
            # In the new SDK, 'model' or 'user' is standard. Let's make sure it's one of them.
            if role not in ["user", "model"]:
                role = "user"
                
            text = msg.get("text", "")
            if not text and "parts" in msg and isinstance(msg["parts"], list) and len(msg["parts"]) > 0:
                part = msg["parts"][0]
                text = part.get("text", "") if isinstance(part, dict) else str(part)
                
            contents.append({"role": role, "parts": [{"text": text}]})

        # Append the new user message
        contents.append({"role": "user", "parts": [{"text": request.message}]})

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION
            )
        )

        return {"response": response.text}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")
