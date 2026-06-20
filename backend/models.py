from pydantic import BaseModel, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

class PointLocation(BaseModel):
    type: Literal['Point'] = 'Point'
    coordinates: List[float] # [longitude, latitude]

class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

class SocialLinks(BaseModel):
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None

class PriceRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None

class VendorProfile(BaseModel):
    businessName: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[PointLocation] = None
    address: Optional[Address] = None
    socialLinks: Optional[SocialLinks] = None
    qualifications: Optional[List[str]] = []
    priceRange: Optional[PriceRange] = None
    subscriptionTier: Literal['basic', 'premium'] = 'basic'
    isFeatured: bool = False
    isVerified: bool = False
    averageRating: float = 0.0
    reviewCount: int = 0

class UserCreate(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    phoneNumber: str
    role: Literal['customer', 'vendor', 'admin'] = 'customer'

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserInDB(BaseModel):
    id: str
    fullName: str
    email: EmailStr
    hashed_password: str
    role: str
    vendorProfile: Optional[VendorProfile] = None
    reset_otp: Optional[str] = None
    reset_otp_expiry: Optional[datetime] = None
    profile_picture: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    fullName: str
    email: EmailStr
    role: str
    vendorProfile: Optional[VendorProfile] = None
    profile_picture: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class GoogleAuthRequest(BaseModel):
    token: str
