from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime, timezone
from database import reviews_collection, bookings_collection, users_collection
from dependencies import get_current_user

router = APIRouter()

class ReviewCreate(BaseModel):
    bookingId: str
    vendorId: str
    rating: int = Field(..., ge=1, le=5)
    comment: str

@router.post("")
async def create_review(review_data: ReviewCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can leave reviews")
    
    customer_id = current_user.get("user_id")

    # Verify the booking belongs to this customer and is completed
    booking = await bookings_collection.find_one({
        "_id": ObjectId(review_data.bookingId),
        "customerId": customer_id
    })

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.get("status") != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only review completed bookings")

    if booking.get("isReviewed", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking is already reviewed")

    # Insert Review
    review_doc = {
        "bookingId": review_data.bookingId,
        "vendorId": review_data.vendorId,
        "customerId": customer_id,
        "rating": review_data.rating,
        "comment": review_data.comment,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await reviews_collection.insert_one(review_doc)

    # Mark booking as reviewed
    await bookings_collection.update_one(
        {"_id": ObjectId(review_data.bookingId)},
        {"$set": {"isReviewed": True}}
    )

    # Recalculate Vendor Average Rating
    reviews_cursor = reviews_collection.find({"vendorId": review_data.vendorId})
    all_reviews = await reviews_cursor.to_list(length=1000)
    
    total_reviews = len(all_reviews)
    if total_reviews > 0:
        avg_rating = sum(r["rating"] for r in all_reviews) / total_reviews
    else:
        avg_rating = 0.0

    await users_collection.update_one(
        {"_id": ObjectId(review_data.vendorId)},
        {"$set": {
            "vendorProfile.averageRating": round(avg_rating, 1),
            "vendorProfile.totalReviews": total_reviews
        }}
    )

    return {"message": "Review submitted successfully"}

@router.get("/vendor/{vendor_id}")
async def get_vendor_reviews(vendor_id: str):
    reviews_cursor = reviews_collection.find({"vendorId": vendor_id}).sort("createdAt", -1)
    reviews = await reviews_cursor.to_list(length=100)
    
    formatted_reviews = []
    for r in reviews:
        customer = await users_collection.find_one({"_id": ObjectId(r["customerId"])})
        customer_name = customer.get("fullName", "Unknown Customer") if customer else "Unknown Customer"
        
        formatted_reviews.append({
            "_id": str(r["_id"]),
            "bookingId": r["bookingId"],
            "vendorId": r["vendorId"],
            "customerId": r["customerId"],
            "customerName": customer_name,
            "rating": r["rating"],
            "comment": r["comment"],
            "createdAt": r.get("createdAt")
        })
        
    return formatted_reviews

