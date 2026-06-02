import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

# Fixed to match the exact filename from image_3bff24.png
from discord_bot import start_bot, stop_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB on startup
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.tbd_dictionary  # Database name
    
    # Get Discord Token and start the bot in the background
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN environment variable is missing!")
    else:
        logger.info("Starting Discord bot...")
        asyncio.create_task(start_bot(token, db))
        
    yield
    
    # Clean up and shut down the bot when the server stops
    logger.info("Shutting down Discord bot...")
    await stop_bot()
    client.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "TBD Backend is running successfully!"}
