from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager
from database import init_db
from routers import auth, vendors, admin, customers, payments, bookings, reviews, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to DB and ensure indexes
    await init_db()
    # Ensure static uploads directory exists
    os.makedirs("static/uploads", exist_ok=True)
    yield
    # Shutdown: Add any cleanup logic here
    print("Shutting down application...")

app = FastAPI(
    title="Micro-Business Service Marketplace",
    description="FastAPI Backend for the vendor marketplace with geospatial search.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(vendors.router, prefix="/api/vendors", tags=["Vendors"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["Bookings"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])

@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "message": "FastAPI is running and ready to serve!"}
