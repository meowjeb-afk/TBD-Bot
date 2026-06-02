"""Discord bot for TBD Dictionary. Runs as background task inside FastAPI."""
import io
import logging
import uuid
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from image_generator import generate_card_image, GENERATED_DIR

logger = logging.getLogger(__name__)

_bot: commands.Bot | None = None
_ready = False

def is_running() -> bool:
    return _ready and _bot is not None and not _bot.is_closed()

def _build_bot(db) -> commands.Bot:
    """Builds the bot and attaches the database handle directly to it."""
    intents = discord.Intents.default()
    intents.message_content = False
    bot = commands.Bot(command_prefix="!", intents=intents)

    # Attach the cloud database handle directly to the bot object
    bot.db = db

    # === UPDATE THIS WITH YOUR ACTUAL DISCORD SERVER ID ===
    DEV_GUILD_ID = 1469032638395191298 
    # ======================================================

    @bot.event
    async def setup_hook():
        try:
            guild = discord.Object(id=DEV_GUILD_ID)
            
            # Sync exclusively to your private developer guild for instant updates
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            
            logger.info(f"Instant Guild Sync Complete! Synced {len(synced)} commands.")
        except Exception as e:
            logger.exception(f"Failed to sync slash commands: {e}")

    @bot.event
    async def on_ready():
        global _ready
        _ready = True
        logger.info(f"Discord bot ready as {bot.user}")

    @bot.tree.command(name="add", description="Add a word to the TBD dictionary")
    async def add_cmd(interaction: discord.Interaction, word: str, definition: str):
        await interaction.response.defer(thinking=True)
        
        try:
            # FIX: Use the secure bot-attached database reference
            db = bot.db
            word_clean = word.strip()
            word_lower = word_clean.lower()
            
            logger.info(f"DEBUG: Starting add process for {word_lower}")

            existing = await db.words.find_one({"word_lower": word_lower})
            if existing:
                await interaction.followup.send(f"`{word_clean}` is already in the dictionary.")
                return

            posted_by = interaction.user.display_name
            count = await db.words.count_documents({})
            pose_index = count % 6

            logger.info("DEBUG: Calling generate_card_image")
            image_file = await generate_card_image(
                word=word_clean, definition=definition.strip(),
                posted_by=posted_by, pose_index=pose_index,
            )

            doc = {
                "id": str(uuid.uuid4()),
                "word": word_clean,
                "word_lower": word_lower,
                "definition": definition.strip(),
                "posted_by": posted_by,
                "discord_user_id": str(interaction.user.id),
                "image_file": image_file,
                "upvotes": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.words.insert_one(doc)

            path = GENERATED_DIR / image_file
            with open(path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=f"{word_lower}.png")
            await interaction.followup.send(
                content=f"**{word_clean}** added to the dictionary!",
                file=file,
            )
            
        except Exception as e:
            logger.error(f"❌ COMMAND ERROR: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}")

    @bot.tree.command(name="lookup", description="Look up a word")
    async def lookup_cmd(interaction: discord.Interaction, word: str):
        await interaction.response.defer(thinking=True)
        try:
            # FIX: Use the secure bot-attached database reference
            db = bot.db
            doc = await db.words.find_one({"word_lower": word.strip().lower()})
            if not doc:
                await interaction.followup.send(f"`{word}` not found.")
                return
            
            path = GENERATED_DIR / doc["image_file"] if doc.get("image_file") else None
            if path and path.exists():
                with open(path, "rb") as f:
                    data = f.read()
                file = discord.File(io.BytesIO(data), filename=f"{doc['word_lower']}.png")
                await interaction.followup.send(content=f"**{doc['word']}**", file=file)
            else:
                await interaction.followup.send(f"**{doc['word']}** — {doc['definition']}")
        except Exception as e:
            logger.error(f"❌ LOOKUP ERROR: {e}", exc_info=True)
            await interaction.followup.send("Error looking up word.")

    @bot.tree.command(name="list", description="List all words in the TBD dictionary")
    async def list_cmd(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            # FIX: Use the secure bot-attached database reference
            db = bot.db
            cursor = db.words.find({}, {"word": 1})
            words_list = [doc["word"] for doc in await cursor.to_list(length=100)]
            
            if not words_list:
                await interaction.followup.send("The dictionary is currently empty.")
                return
                
            formatted_list = ", ".join(f"`{w}`" for w in words_list)
            await interaction.followup.send(f"📚 **Dictionary Words:**\n{formatted_list}")
        except Exception as e:
            logger.error(f"❌ LIST ERROR: {e}", exc_info=True)
            await interaction.followup.send("Error retrieving words list.")

    return bot

async def start_bot(token: str, db):
    """Start the Discord bot."""
    global _bot
    _bot = _build_bot(db)
    try:
        await _bot.start(token)
    except Exception as e:
        logger.exception(f"Discord bot crashed: {e}")

async def stop_bot():
    global _bot, _ready
    _ready = False
    if _bot and not _bot.is_closed():
        try:
            await _bot.close()
        except Exception:
            pass
