from fastapi import APIRouter, Depends
from typing import List
from database import users_collection
from dependencies import get_current_admin

router = APIRouter()

@router.get("/users")
async def get_all_users(admin_user: dict = Depends(get_current_admin)):
    """
    Fetch all users from the database. Only accessible by admins.
    """
    users_cursor = users_collection.find({})
    users = await users_cursor.to_list(length=None)
    
    formatted_users = []
    for user in users:
        formatted_users.append({
            "id": str(user["_id"]),
            "email": user.get("email"),
            "role": user.get("role"),
            "vendorProfile": user.get("vendorProfile"),
            "created_at": user.get("created_at")
        })
        
    return formatted_users
