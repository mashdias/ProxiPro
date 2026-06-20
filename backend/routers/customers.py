from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
import os
import shutil
import uuid
from typing import Optional
from pydantic import BaseModel
from bson import ObjectId
from database import users_collection
from dependencies import get_current_user
from datetime import datetime, timezone

router = APIRouter()

class CustomerProfileUpdate(BaseModel):
    fullName: str
    phoneNumber: Optional[str] = None
    address: Optional[str] = None
    profilePhoto: Optional[str] = None

@router.get("/profile")
async def get_customer_profile(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can access this")
        
    user_id = ObjectId(current_user.get("user_id"))
    user = await users_collection.find_one({"_id": user_id}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    customer_profile = user.get("customerProfile", {})
    if customer_profile is None:
        customer_profile = {}
    
    return {
        "fullName": user.get("fullName", ""),
        "email": user.get("email", ""),
        "phoneNumber": customer_profile.get("phoneNumber", ""),
        "address": customer_profile.get("address", ""),
        "profilePhoto": customer_profile.get("profilePhoto") or user.get("profile_picture", ""),
        "isVIP": customer_profile.get("isVIP", False)
    }

@router.put("/profile")
async def update_customer_profile(profile: CustomerProfileUpdate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can update their profile")

    user_id = ObjectId(current_user.get("user_id"))
    
    # Initialize customerProfile if it is null to prevent MongoDB WriteError
    await users_collection.update_one(
        {"_id": user_id, "customerProfile": None},
        {"$set": {"customerProfile": {}}}
    )
    
    result = await users_collection.update_one(
        {"_id": user_id},
        {"$set": {
            "fullName": profile.fullName,
            "customerProfile.phoneNumber": profile.phoneNumber,
            "customerProfile.address": profile.address,
            "customerProfile.profilePhoto": profile.profilePhoto
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": "Profile updated successfully"}

@router.post("/profile/upload")
async def upload_profile_photo(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can upload photos")
        
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join("static/uploads", filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"url": f"http://localhost:8000/static/uploads/{filename}"}

@router.post("/saved-vendors/{vendor_id}")
async def save_vendor(vendor_id: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can save vendors")
    user_id = ObjectId(current_user.get("user_id"))
    await users_collection.update_one(
        {"_id": user_id},
        {"$addToSet": {"savedVendors": vendor_id}}
    )
    return {"message": "Vendor saved successfully"}

@router.delete("/saved-vendors/{vendor_id}")
async def remove_saved_vendor(vendor_id: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can remove saved vendors")
    user_id = ObjectId(current_user.get("user_id"))
    await users_collection.update_one(
        {"_id": user_id},
        {"$pull": {"savedVendors": vendor_id}}
    )
    return {"message": "Vendor removed successfully"}

@router.get("/saved-vendors")
async def get_saved_vendors(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can view saved vendors")
    user_id = ObjectId(current_user.get("user_id"))
    user = await users_collection.find_one({"_id": user_id}, {"savedVendors": 1})
    saved_vendors_ids = user.get("savedVendors", [])
    
    if not saved_vendors_ids:
        return []
        
    object_ids = []
    for vid in saved_vendors_ids:
        try:
            object_ids.append(ObjectId(vid))
        except Exception:
            pass
            
    cursor = users_collection.find({"_id": {"$in": object_ids}}, {"password": 0})
    vendors = await cursor.to_list(length=100)
    
    results = []
    for v in vendors:
        v["_id"] = str(v["_id"])
        results.append(v)
    return results

@router.post("/upgrade-vip")
async def upgrade_to_vip(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can upgrade to VIP")
    
    user_id = ObjectId(current_user.get("user_id"))
    
    # Initialize customerProfile if it is null
    await users_collection.update_one(
        {"_id": user_id, "customerProfile": None},
        {"$set": {"customerProfile": {}}}
    )
    
    result = await users_collection.update_one(
        {"_id": user_id},
        {"$set": {
            "customerProfile.isVIP": True,
            "customerProfile.vipPaymentDate": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    return {"message": "Successfully upgraded to VIP"}
