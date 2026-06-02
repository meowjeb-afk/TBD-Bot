import certifi
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

# Importing start/stop functions from your flat directory
from discord_bot import start_bot, stop_bot

# Add this before creating your AsyncIOMotorClient
os.environ["SSL_CERT_FILE"] = certifi.where()

# Set up logging to show what is happening during startup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # HARDCODED for testing purposes only
    mongo_uri = "mongodb+srv://pixl:yCcwerX55ekSla0y@tbd.tvvtptx.mongodb.net/?appName=TBD"
    
    logger.info("✅ Attempting to connect to MongoDB Atlas with hardcoded URI.")
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client.tbd_dictionary
    # ... rest of lifespan
    
    # Diagnostic: Check if we are accidentally using the local fallback
    if "localhost" in mongo_uri:
        logger.warning("⚠️ WARNING: Using fallback localhost database connection!")
    else:
        logger.info("✅ Attempting to connect to MongoDB Atlas cluster.")

    # 2. Connect to MongoDB
    client = AsyncIOMotorClient(mongo_uri)
    db = client.tbd_dictionary  # Database name
    
    # 3. Get Discord Token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN environment variable is missing!")
    else:
        logger.info("🚀 Starting Discord bot...")
        
        # 4. Start the bot as a background task
        bot_task = asyncio.create_task(start_bot(token, db))
        
        # 5. Add a callback to catch the specific 'Task exception' that was getting swallowed
        bot_task.add_done_callback(
            lambda t: logger.error(f"❌ Bot task crashed: {t.exception()}") if t.exception() else None
        )
        
    yield
    
    # 6. Clean up on shutdown
    logger.info("Shutting down Discord bot...")
    await stop_bot()
    client.close()

# Initialize FastAPI with the lifespan manager
app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "TBD Backend is running successfully!"}
