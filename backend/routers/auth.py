import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt
from database import users_collection
from models import UserCreate, UserLogin, UserResponse, Token, ForgotPasswordRequest, ResetPasswordRequest, GoogleAuthRequest
import random
import string
import httpx
from utils.mailer import send_email

router = APIRouter()

# Setup password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET", "super_secret_jwt_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10080 # 7 days for testing

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    # Check if user already exists
    existing_user = await users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    hashed_password = get_password_hash(user.password)
    
    # Create user dictionary
    user_dict = {
        "fullName": user.fullName,
        "email": user.email,
        "password": hashed_password,
        "role": user.role,
        "vendorProfile": {"phoneNumber": user.phoneNumber} if user.role == "vendor" else None,
        "customerProfile": {"phoneNumber": user.phoneNumber} if user.role == "customer" else None,
        "created_at": datetime.now(timezone.utc)
    }
    
    # Insert to DB
    result = await users_collection.insert_one(user_dict)
    
    # Send Welcome Email (Non-blocking)
    try:
        html_template = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #4F46E5;">Welcome to ProxiPro, {user.fullName}! 🎉</h2>
                    <p>Hi {user.fullName},</p>
                    <p>Welcome to ProxiPro! Your gateway to top-tier local services.</p>
                    <p>We're absolutely thrilled to have you on board. Start exploring and booking the best talent in your area today.</p>
                    <br>
                    <p>Best regards,<br><strong>The ProxiPro Team</strong></p>
                </div>
            </body>
        </html>
        """
        # We await it since it uses asyncio.to_thread internally so it won't block the main event loop
        await send_email(to_email=user.email, subject="Welcome to ProxiPro! 🎉", html_content=html_template)
    except Exception as e:
        print(f"Non-critical error: Failed to send welcome email to {user.email}: {e}")
    
    # Return response
    return UserResponse(
        id=str(result.inserted_id),
        fullName=user.fullName,
        email=user.email,
        role=user.role,
        vendorProfile=None
    )

@router.post("/login", response_model=Token)
async def login_user(form_data: OAuth2PasswordRequestForm = Depends()):
    # Find user in DB
    db_user = await users_collection.find_one({"email": form_data.username})
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(form_data.password, db_user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Determine the name to include in JWT
    display_name = db_user.get("fullName", "")
    if db_user.get("role") == "vendor" and db_user.get("vendorProfile"):
        display_name = db_user["vendorProfile"].get("businessName", display_name)

    # Determine the profile picture to include in JWT
    profile_pic = db_user.get("profile_picture")
    if db_user.get("role") == "customer" and db_user.get("customerProfile"):
        profile_pic = db_user["customerProfile"].get("profilePhoto", profile_pic)
    elif db_user.get("role") == "vendor" and db_user.get("vendorProfile"):
        profile_pic = db_user["vendorProfile"].get("profilePhoto", profile_pic)

    access_token = create_access_token(
        data={"sub": db_user["email"], "role": db_user["role"], "user_id": str(db_user["_id"]), "name": display_name, "profile_picture": profile_pic},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    user = await users_collection.find_one({"email": request.email})
    if not user:
        # Prevent email enumeration by returning success even if user not found
        return {"message": "If that email is registered, you will receive a reset OTP shortly."}
    
    # Generate 6-digit OTP
    otp = ''.join(random.choices(string.digits, k=6))
    expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    # Update DB with OTP and expiry
    await users_collection.update_one(
        {"email": request.email},
        {"$set": {"reset_otp": otp, "reset_otp_expiry": expiry}}
    )
    
    # Send email
    html_template = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #4F46E5;">Password Reset Request</h2>
                <p>Hello,</p>
                <p>We received a request to reset your password for ProxiPro. Here is your 6-digit OTP:</p>
                <h1 style="font-size: 32px; letter-spacing: 5px; color: #4F46E5; text-align: center; background-color: #f3f4f6; padding: 10px; border-radius: 8px;">{otp}</h1>
                <p>This code will expire in 15 minutes.</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
                <br>
                <p>Best regards,<br><strong>The ProxiPro Team</strong></p>
            </div>
        </body>
    </html>
    """
    
    try:
        await send_email(to_email=request.email, subject="Password Reset OTP", html_content=html_template)
    except Exception as e:
        print(f"Failed to send reset OTP to {request.email}: {e}")
        # We don't fail the request so the user flow remains consistent
        
    return {"message": "If that email is registered, you will receive a reset OTP shortly."}

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    user = await users_collection.find_one({"email": request.email})
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request")
    
    # Verify OTP exists
    if not user.get("reset_otp") or not user.get("reset_otp_expiry"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OTP requested or expired")
    
    # Verify OTP matches
    if user["reset_otp"] != request.otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    
    # Verify OTP hasn't expired
    # Need to make sure the datetime stored is timezone-aware or treat both as UTC
    expiry = user["reset_otp_expiry"]
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
        
    if datetime.now(timezone.utc) > expiry:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired")
    
    # Update password and clear OTP
    hashed_password = get_password_hash(request.new_password)
    await users_collection.update_one(
        {"email": request.email},
        {
            "$set": {"password": hashed_password},
            "$unset": {"reset_otp": "", "reset_otp_expiry": ""}
        }
    )
    
    return {"message": "Password successfully reset"}

@router.post("/google", response_model=Token)
async def google_auth(request: GoogleAuthRequest):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="Google Client ID not configured")
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={request.token}")
            
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
            
        id_info = response.json()
        
        # Verify the audience matches our client ID
        if id_info.get("aud") != client_id:
            raise HTTPException(status_code=401, detail="Invalid audience")
            
        email = id_info.get("email")
        name = id_info.get("name")
        picture = id_info.get("picture")
        
        if not email:
            raise HTTPException(status_code=400, detail="Google token missing email")
            
        # Find user
        db_user = await users_collection.find_one({"email": email})
        
        if db_user:
            # Determine the current true DB picture
            db_pic = db_user.get("profile_picture")
            if db_user.get("role") == "customer" and db_user.get("customerProfile"):
                db_pic = db_user["customerProfile"].get("profilePhoto") or db_pic
            elif db_user.get("role") == "vendor" and db_user.get("vendorProfile"):
                db_pic = db_user["vendorProfile"].get("profilePhoto") or db_pic

            # DO NOT overwrite existing custom database picture with Google picture
            if not db_pic and picture:
                await users_collection.update_one(
                    {"_id": db_user["_id"]},
                    {"$set": {"profile_picture": picture}}
                )
                db_user["profile_picture"] = picture
            else:
                # Retain the existing DB picture for the JWT token
                picture = db_pic
        else:
            # Register new user
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            hashed_password = get_password_hash(random_password)
            
            user_dict = {
                "fullName": name,
                "email": email,
                "password": hashed_password,
                "role": "customer",  # Default role for google sign-in
                "vendorProfile": None,
                "customerProfile": None,
                "profile_picture": picture,
                "created_at": datetime.now(timezone.utc)
            }
            
            result = await users_collection.insert_one(user_dict)
            db_user = user_dict
            db_user["_id"] = result.inserted_id
            
        # Determine display name
        display_name = db_user.get("fullName", name or "User")
        if db_user.get("role") == "vendor" and db_user.get("vendorProfile"):
            display_name = db_user["vendorProfile"].get("businessName", display_name)

        # Generate JWT token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": db_user["email"], "role": db_user["role"], "user_id": str(db_user["_id"]), "name": display_name, "profile_picture": picture},
            expires_delta=access_token_expires
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

