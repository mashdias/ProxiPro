import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/micro_business_db")

# Initialize Motor Client
client = AsyncIOMotorClient(MONGO_URI)
db = client.micro_business_db

# Collections
vendors_collection = db.get_collection("vendors")
users_collection = db.get_collection("usersTree")
settings_collection = db.get_collection("settings")
bookings_collection = db.get_collection("bookings")
reviews_collection = db.get_collection("reviews")

async def init_db():
    try:
        # Ping the database to confirm connection
        await client.admin.command('ping')
        print("MongoDB connected successfully via Motor!")
        
        # Create 2dsphere index on the location field for fast geospatial queries
        await users_collection.create_index([("vendorProfile.location", "2dsphere")])
        print("Geospatial index ensured on usersTree collection.")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
