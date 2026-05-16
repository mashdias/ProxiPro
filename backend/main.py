from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager
from database import init_db
from routers import auth, vendors, admin

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
    allow_origins=["http://localhost:3000"],
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

@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "message": "FastAPI is running and ready to serve!"}
