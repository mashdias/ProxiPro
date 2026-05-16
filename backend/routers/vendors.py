from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
import os
import shutil
import uuid
from typing import Optional
from pydantic import BaseModel
from bson import ObjectId
from database import users_collection
from dependencies import get_current_user

router = APIRouter()

class VendorProfileUpdate(BaseModel):
    businessName: str
    category: str
    description: str
    latitude: float
    longitude: float
    phoneNumber: Optional[str] = None
    whatsapp: Optional[str] = None
    facebook: Optional[str] = None
    profilePhoto: Optional[str] = None

@router.get("/profile")
async def get_vendor_profile(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only vendors can access this")
        
    user_id = ObjectId(current_user.get("user_id"))
    user = await users_collection.find_one({"_id": user_id}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    vendor_profile = user.get("vendorProfile")
    if not vendor_profile:
        return {} # Return empty profile
        
    # Format for frontend
    return {
        "businessName": vendor_profile.get("businessName", ""),
        "category": vendor_profile.get("category", ""),
        "description": vendor_profile.get("description", ""),
        "latitude": vendor_profile.get("location", {}).get("coordinates", [0,0])[1] if vendor_profile.get("location") else "",
        "longitude": vendor_profile.get("location", {}).get("coordinates", [0,0])[0] if vendor_profile.get("location") else "",
        "phoneNumber": vendor_profile.get("phoneNumber", ""),
        "whatsapp": vendor_profile.get("whatsapp", ""),
        "facebook": vendor_profile.get("facebook", ""),
        "profilePhoto": vendor_profile.get("profilePhoto", "")
    }

@router.put("/profile")
async def update_vendor_profile(profile: VendorProfileUpdate, current_user: dict = Depends(get_current_user)):
    # 1. Protect: Ensure only vendors can access this
    if current_user.get("role") != "vendor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only vendors can update their profile"
        )

    # 2. Format: Build the GeoJSON structure
    vendor_profile_data = {
        "businessName": profile.businessName,
        "category": profile.category,
        "description": profile.description,
        "location": {
            "type": "Point",
            "coordinates": [profile.longitude, profile.latitude] # GeoJSON is always [longitude, latitude]
        },
        "phoneNumber": profile.phoneNumber,
        "whatsapp": profile.whatsapp,
        "facebook": profile.facebook,
        "profilePhoto": profile.profilePhoto
    }

    # 3. Save: Update the user's document in MongoDB
    user_id = ObjectId(current_user.get("user_id"))
    result = await users_collection.update_one(
        {"_id": user_id},
        {"$set": {"vendorProfile": vendor_profile_data}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": "Profile updated successfully"}

@router.post("/profile/upload")
async def upload_profile_photo(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only vendors can upload photos")
        
    # Generate unique filename
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join("static/uploads", filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"url": f"http://localhost:8000/static/uploads/{filename}"}

@router.get("/search")
async def search_vendors(lat: float, lng: float, radius_km: float = 5.0, category: str = None):
    """
    Search vendors based on geospatial proximity.
    """
    max_distance_meters = radius_km * 1000

    query = {
        "role": "vendor",
        "vendorProfile.location": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "$maxDistance": max_distance_meters
            }
        }
    }

    if category and category.lower() != "all":
        query["vendorProfile.category"] = category

    cursor = users_collection.find(query, {"password": 0})
    vendors = await cursor.to_list(length=100)
    
    results = []
    for v in vendors:
        v["_id"] = str(v["_id"])
        results.append(v)
        
    return results

@router.get("/{vendor_id}")
async def get_vendor(vendor_id: str):
    return {"message": f"Get vendor details for {vendor_id}"}
