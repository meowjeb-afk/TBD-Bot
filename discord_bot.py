"""Discord bot for TBD Dictionary. Runs as background task inside FastAPI."""
import io
import json
import logging
import uuid
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from bson import json_util

from image_generator import generate_card_image, GENERATED_DIR

logger = logging.getLogger(__name__)

# Explicit developer security account check
DEVELOPER_USER_ID = 552956853147926532 

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

    # === DEV SERVER ID FOR INSTANT COMMAND SYNCING ===
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

    # ==========================================
    # COMMAND 1: SLASH COMMAND - /add
    # ==========================================
    @bot.tree.command(name="add", description="Add a word to the TBD dictionary")
    async def add_cmd(interaction: discord.Interaction, word: str, definition: str):
        await interaction.response.defer(thinking=True)
        
        try:
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

    # ==========================================
    # COMMAND 2: SLASH COMMAND - /lookup
    # ==========================================
    @bot.tree.command(name="lookup", description="Look up a word")
    async def lookup_cmd(interaction: discord.Interaction, word: str):
        await interaction.response.defer(thinking=True)
        try:
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

    # ==========================================
    # COMMAND 3: SLASH COMMAND - /list
    # ==========================================
    @bot.tree.command(name="list", description="List all words in the TBD dictionary")
    async def list_cmd(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            db = bot.db
            cursor = db.words.find({}, {"word": 1}).sort("word", 1)
            words_list = [doc["word"] for doc in await cursor.to_list(length=100)]
            
            if not words_list:
                await interaction.followup.send("The dictionary is currently empty.")
                return
                
            formatted_list = ", ".join(f"`{w}`" for w in words_list)
            
            if len(formatted_list) > 1900:
                formatted_list = formatted_list[:1850] + "... and more!"

            await interaction.followup.send(f"📚 **Dictionary Words:**\n{formatted_list}")
        except Exception as e:
            logger.error(f"❌ LIST ERROR: {e}", exc_info=True)
            await interaction.followup.send("Error retrieving words list.")

    # ==========================================
    # COMMAND 4: SLASH COMMAND - /deleteword
    # ==========================================
    @bot.tree.command(
        name="deleteword", 
        description="[TESTING ONLY] Force delete a word entry from the database."
    )
    @app_commands.describe(word="The exact dictionary word entry you wish to wipe out.")
    async def deleteword_command(interaction: discord.Interaction, word: str):
        if interaction.user.id != DEVELOPER_USER_ID:
            await interaction.response.send_message(
                "❌ **Permission Denied:** This destructive action is locked exclusively to developers during testing.",
                ephemeral=True
            )
            return

        if bot.db is None:
            await interaction.response.send_message("❌ **Database Offline:** The bot lost its active link connection.", ephemeral=True)
            return

        target_word = word.strip()
        await interaction.response.defer(ephemeral=True)

        try:
            query = {"word": {"$regex": f"^{target_word}$", "$options": "i"}}
            result = await bot.db.words.delete_one(query)
            
            if result.deleted_count > 0:
                await interaction.followup.send(
                    f"🗑️ **Testing Purge Successful:**\n"
                    f"The word entry matching `“{target_word}”` was vaporized from the collection.",
                    ephemeral=True
                )
                logger.info(f"Developer {interaction.user} forcefully dropped word '{target_word}' via slash route.")
            else:
                await interaction.followup.send(
                    f"❓ **Wipe Missed:** Could not find an entry matching `“{target_word}”` inside the database. Run `/debuglist` to audit keys.",
                    ephemeral=True
                )
        except Exception as mongo_error:
            logger.error(f"MongoDB pipeline broke during testing wipe: {mongo_error}")
            await interaction.followup.send(f"❌ **Database Error:** `{str(mongo_error)}`", ephemeral=True)

    # ==========================================
    # COMMAND 5: SLASH COMMAND - /debuglist
    # ==========================================
    @bot.tree.command(
        name="debuglist", 
        description="[TESTING ONLY] Inspect raw database structure."
    )
    async def debuglist_command(interaction: discord.Interaction):
        if interaction.user.id != DEVELOPER_USER_ID:
            await interaction.response.send_message("❌ **Permission Denied.**", ephemeral=True)
            return

        if bot.db is None:
            await interaction.response.send_message("❌ **Database Connection Unavailable.**", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            cursor = bot.db.words.find().sort("_id", -1).limit(1)
            documents = await cursor.to_list(length=1)

            if not documents:
                await interaction.followup.send("⚠️ Database collection is empty or collection name is incorrect.", ephemeral=True)
                return
            
            raw_dump = json.dumps(documents, default=json_util.default, indent=2)
            
            if len(raw_dump) > 1900:
                raw_dump = raw_dump[:1900] + "\n...[Truncated]"

            await interaction.followup.send(f"🔍 **Raw Entry Structure:**\n```json\n{raw_dump}\n```", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Diagnostic error: `{str(e)}`", ephemeral=True)

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
