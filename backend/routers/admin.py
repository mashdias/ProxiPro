from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId
from pydantic import BaseModel
from database import users_collection, settings_collection
from dependencies import get_current_admin
from routers.auth import get_password_hash
from datetime import datetime, timezone

router = APIRouter()

class UserUpdate(BaseModel):
    fullName: str
    email: str
    role: str

class AdminCreate(BaseModel):
    fullName: str
    email: str
    password: str

class SettingsUpdate(BaseModel):
    vendorPremiumFee: float
    customerVipFee: float

@router.get("/users")
async def get_all_users(admin_user: dict = Depends(get_current_admin)):
    """
    Fetch all users from the database. Only accessible by admins.
    """
    users_cursor = users_collection.find({})
    users = await users_cursor.to_list(length=1000)
    
    formatted_users = []
    for user in users:
        profile = user.get("vendorProfile") or {}
        customer_profile = user.get("customerProfile") or {}
        formatted_users.append({
            "_id": str(user["_id"]),
            "fullName": user.get("fullName", ""),
            "email": user.get("email"),
            "role": user.get("role"),
            "businessName": profile.get("businessName", ""),
            "isPremium": profile.get("isPremium", False),
            "paymentStatus": profile.get("paymentStatus", "Pending"),
            "isVIP": customer_profile.get("isVIP", False),
            "vipPaymentDate": customer_profile.get("vipPaymentDate"),
            "premiumPaymentDate": profile.get("premiumPaymentDate")
        })
        
    return formatted_users

@router.put("/users/{user_id}")
async def update_user(user_id: str, user_update: UserUpdate, admin_user: dict = Depends(get_current_admin)):
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "fullName": user_update.fullName,
            "email": user_update.email,
            "role": user_update.role
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User updated successfully"}

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin_user: dict = Depends(get_current_admin)):
    result = await users_collection.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

@router.post("/create-admin")
async def create_admin(admin_data: AdminCreate, admin_user: dict = Depends(get_current_admin)):
    existing_user = await users_collection.find_one({"email": admin_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(admin_data.password)
    
    user_dict = {
        "fullName": admin_data.fullName,
        "email": admin_data.email,
        "password": hashed_password,
        "role": "admin",
        "vendorProfile": None,
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await users_collection.insert_one(user_dict)
    return {"message": "Admin created successfully", "id": str(result.inserted_id)}

@router.get("/vendors")
async def get_all_vendors(admin_user: dict = Depends(get_current_admin)):
    cursor = users_collection.find({"role": "vendor"})
    vendors = await cursor.to_list(length=1000)
    
    formatted_vendors = []
    for v in vendors:
        profile = v.get("vendorProfile", {})
        if profile is None:
            profile = {}
        formatted_vendors.append({
            "_id": str(v["_id"]),
            "fullName": v.get("fullName", ""),
            "businessName": profile.get("businessName", ""),
            "email": v.get("email", ""),
            "isPremium": profile.get("isPremium", False),
            "paymentStatus": profile.get("paymentStatus", "Pending")
        })
    return formatted_vendors

@router.patch("/vendors/{vendor_id}/verify")
async def verify_vendor(vendor_id: str, admin_user: dict = Depends(get_current_admin)):
    result = await users_collection.update_one(
        {"_id": ObjectId(vendor_id)},
        {"$set": {
            "vendorProfile.isPremium": True,
            "vendorProfile.paymentStatus": "Manually Verified",
            "vendorProfile.premiumPaymentDate": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {"message": "Vendor verified successfully"}

@router.patch("/vendors/{vendor_id}/revoke")
async def revoke_vendor(vendor_id: str, admin_user: dict = Depends(get_current_admin)):
    result = await users_collection.update_one(
        {"_id": ObjectId(vendor_id)},
        {"$set": {
            "vendorProfile.isPremium": False,
            "vendorProfile.paymentStatus": "Pending"
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
@router.get("/admins")
async def get_all_admins(admin_user: dict = Depends(get_current_admin)):
    cursor = users_collection.find({"role": "admin"})
    admins = await cursor.to_list(length=1000)
    
    formatted = []
    for a in admins:
        formatted.append({
            "_id": str(a["_id"]),
            "fullName": a.get("fullName", ""),
            "email": a.get("email", "")
        })
    return formatted

@router.delete("/admins/{admin_id}")
async def delete_admin(admin_id: str, admin_user: dict = Depends(get_current_admin)):
    target_admin = await users_collection.find_one({"_id": ObjectId(admin_id)})
    if not target_admin:
        raise HTTPException(status_code=404, detail="Admin not found")
        
    if target_admin.get("email") == "admin@proxipro.com":
        raise HTTPException(status_code=403, detail="Cannot delete the primary admin account")
        
    if str(target_admin["_id"]) == str(admin_user.get("user_id")):
        raise HTTPException(status_code=403, detail="Cannot delete your own admin account")
        
    result = await users_collection.delete_one({"_id": ObjectId(admin_id)})
    return {"message": "Admin deleted successfully"}

@router.get("/settings")
async def get_settings():
    settings = await settings_collection.find_one({"_id": "global_settings"})
    if not settings:
        return {"vendorPremiumFee": 2000, "customerVipFee": 500}
    return {
        "vendorPremiumFee": settings.get("vendorPremiumFee", 2000),
        "customerVipFee": settings.get("customerVipFee", 500)
    }

@router.post("/settings")
async def update_settings(settings: SettingsUpdate, admin_user: dict = Depends(get_current_admin)):
    await settings_collection.update_one(
        {"_id": "global_settings"},
        {"$set": {
            "vendorPremiumFee": settings.vendorPremiumFee,
            "customerVipFee": settings.customerVipFee
        }},
        upsert=True
    )
    return {"message": "Settings updated successfully"}
