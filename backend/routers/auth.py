import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt
from database import users_collection
from models import UserCreate, UserLogin, UserResponse, Token

router = APIRouter()

# Setup password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET", "super_secret_jwt_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

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
        "vendorProfile": None,
        "created_at": datetime.now(timezone.utc)
    }
    
    # Insert to DB
    result = await users_collection.insert_one(user_dict)
    
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

    access_token = create_access_token(
        data={"sub": db_user["email"], "role": db_user["role"], "user_id": str(db_user["_id"]), "name": display_name},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
