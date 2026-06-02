import os
import asyncio
import logging
import shutil
from pathlib import Path
import certifi
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient

# Importing start/stop functions
from discord_bot import start_bot, stop_bot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force the application to use the certifi bundle for all SSL operations
os.environ["SSL_CERT_FILE"] = certifi.where()

# Track db globally for our API endpoints to access
database_client = None
db = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global database_client, db
    
    # Retrieve the MONGO_URI from environment variables
    mongo_uri = os.getenv("MONGO_URI")
    
    if not mongo_uri:
        logger.error("❌ MONGO_URI environment variable is missing!")
        yield
        return

    logger.info("✅ Attempting to connect to MongoDB Atlas cluster.")

    database_client = AsyncIOMotorClient(
        mongo_uri,
        tls=True,
        tlsCAFile=certifi.where(),  # This forces Python to use a rock-solid cert bundle
        serverSelectionTimeoutMS=20000
    )
    
    db = database_client.tbd_dictionary
    
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
    if database_client:
        database_client.close()

# Initialize FastAPI
app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "TBD Backend is running successfully!"}


## --- TESTING PURGES / DELETE ROUTE ---

@app.delete("/test/cleanup", status_code=status.HTTP_200_OK)
async def dev_cleanup_route(purge_db: bool = False, purge_images: bool = True):
    """
    A destructive endpoint built purely for local testing.
    - purge_images: Wipes out the 'generated/' folder locally.
    - purge_db: Drops the 'cards' collection from your MongoDB setup.
    """
    # ⚠️ Quick check to prevent accidents in a production cluster
    if os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Testing routes are completely disabled in production environments!"
        )
        
    summary = {}

    # 1. Clear local image files cache
    if purge_images:
        generated_dir = Path(__file__).parent / "generated"
        if generated_dir.exists():
            try:
                # Completely wipe out files inside 'generated' directory
                for item in generated_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                summary["images_purged"] = "Successfully cleared all generated image files."
            except Exception as e:
                summary["images_purged"] = f"Failed to wipe files: {str(e)}"
        else:
            summary["images_purged"] = "Directory path not found."

    # 2. Clear MongoDB dictionary collection documents
    if purge_db:
        if db is not None:
            try:
                # Adjust 'cards' to match whatever your collection name actually is!
                result = await db.cards.delete_many({})
                summary["db_purged"] = f"Successfully dropped {result.deleted_count} items from DB."
            except Exception as e:
                summary["db_purged"] = f"Failed to clear MongoDB data: {str(e)}"
        else:
            summary["db_purged"] = "Database connection is unavailable."

    return {
        "message": "Testing cleanup execution complete.",
        "results": summary
    }
