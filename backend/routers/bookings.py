from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from bson import ObjectId
from database import bookings_collection, users_collection
from dependencies import get_current_user

router = APIRouter()

class BookingCreate(BaseModel):
    vendorId: str
    serviceName: str
    priceAtBooking: float
    bookingDate: str
    customerNotes: Optional[str] = None

class BookingStatusUpdate(BaseModel):
    status: str  # pending, accepted, declined, completed

@router.post("")
async def create_booking(booking: BookingCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can create bookings")

    vendor = await users_collection.find_one({"_id": ObjectId(booking.vendorId), "role": "vendor"})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    customer = await users_collection.find_one({"_id": ObjectId(current_user["_id"])})
    customer_phone = (customer.get("customerProfile") or {}).get("phoneNumber", "") if customer else ""

    booking_doc = {
        "customerId": str(current_user["_id"]),
        "customerName": current_user.get("fullName", "Unknown Customer"),
        "customerPhone": customer_phone,
        "vendorId": booking.vendorId,
        "vendorName": vendor.get("vendorProfile", {}).get("businessName") or vendor.get("fullName", "Unknown Vendor"),
        "serviceName": booking.serviceName,
        "priceAtBooking": booking.priceAtBooking,
        "status": "pending",
        "bookingDate": booking.bookingDate,
        "customerNotes": booking.customerNotes,
        "createdAt": datetime.now(timezone.utc)
    }

    result = await bookings_collection.insert_one(booking_doc)
    booking_doc["_id"] = str(result.inserted_id)
    return booking_doc

@router.get("/customer")
async def get_customer_bookings(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers can fetch their bookings here")

    cursor = bookings_collection.find({"customerId": str(current_user["_id"])}).sort("createdAt", -1)
    bookings = await cursor.to_list(length=100)
    
    for b in bookings:
        b["_id"] = str(b["_id"])
    return bookings

@router.get("/vendor")
async def get_vendor_bookings(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can fetch their bookings here")

    cursor = bookings_collection.find({"vendorId": str(current_user["_id"])}).sort("createdAt", -1)
    bookings = await cursor.to_list(length=100)
    
    for b in bookings:
        b["_id"] = str(b["_id"])
        if not b.get("customerPhone"):
            customer = await users_collection.find_one(
                {"_id": ObjectId(b["customerId"])},
                {"customerProfile.phoneNumber": 1}
            )
            if customer:
                b["customerPhone"] = (customer.get("customerProfile") or {}).get("phoneNumber", "")
    return bookings

@router.patch("/{booking_id}/status")
async def update_booking_status(booking_id: str, status_update: BookingStatusUpdate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Only vendors can update booking status")

    valid_statuses = ["pending", "accepted", "declined", "completed"]
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking["vendorId"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to update this booking")

    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {"status": status_update.status, "updatedAt": datetime.now(timezone.utc)}}
    )

    return {"message": "Booking status updated successfully", "new_status": status_update.status}

@router.get("/vendor/{vendorId}/unavailable-times")
async def get_unavailable_times(vendorId: str, date: str):
    """
    Fetch all booked time slots for a specific vendor on a given date 
    where the status is either pending or accepted.
    """
    query = {
        "vendorId": vendorId,
        "status": {"$in": ["pending", "accepted"]},
        "bookingDate": {"$regex": f"^{date}"}
    }
    cursor = bookings_collection.find(query)
    bookings = await cursor.to_list(length=100)
    
    unavailable_times = []
    for b in bookings:
        booking_datetime = b.get("bookingDate")
        if booking_datetime and "T" in booking_datetime:
            time_part = booking_datetime.split("T")[1][:5] # e.g., "09:00"
            unavailable_times.append(time_part)
            
    return unavailable_times
