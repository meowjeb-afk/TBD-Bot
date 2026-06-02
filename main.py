import os
import asyncio
import logging
import certifi
from contextlib import asynccontextmanager
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

# Importing start/stop functions
from discord_bot import start_bot, stop_bot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force the application to use the certifi bundle for all SSL operations
os.environ["SSL_CERT_FILE"] = certifi.where()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retrieve the MONGO_URI from environment variables
    mongo_uri = os.getenv("MONGO_URI")
    
    if not mongo_uri:
        logger.error("❌ MONGO_URI environment variable is missing!")
        yield
        return

    logger.info("✅ Attempting to connect to MongoDB Atlas cluster.")

    # Update your client initialization in main.py
client = AsyncIOMotorClient(
    mongo_uri,
    tls=True,
    tlsAllowInvalidCertificates=True,
    serverSelectionTimeoutMS=5000, # Reduced to 5s to fail/retry faster
    connectTimeoutMS=5000,
    directConnection=False # Keep False for Replica Sets
)
    
    db = client.tbd_dictionary
    
    # Get Discord Token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN environment variable is missing!")
    else:
        logger.info("🚀 Starting Discord bot...")
        
        # Start the bot as a background task
        bot_task = asyncio.create_task(start_bot(token, db))
        
        # Callback to catch crashes
        bot_task.add_done_callback(
            lambda t: logger.error(f"❌ Bot task crashed: {t.exception()}") if t.exception() else None
        )
        
    yield
    
    # Cleanup
    logger.info("Shutting down Discord bot...")
    await stop_bot()
    client.close()

# Initialize FastAPI
app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "TBD Backend is running successfully!"}
