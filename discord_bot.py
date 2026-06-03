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

DEVELOPER_USER_ID = 552956853147926532 
_bot: commands.Bot | None = None
_ready = False

def is_running() -> bool:
    return _ready and _bot is not None and not _bot.is_closed()

def _build_bot(db) -> commands.Bot:
    # FIX: Start with default intents but explicitly turn off voice state tracking
    intents = discord.Intents.default()
    intents.voice_states = False  # Tells Discord not to expect voice access
    intents.message_content = False
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.db = db
    DEV_GUILD_ID = 1469032638395191298 

    @bot.event
    async def setup_hook():
        try:
            guild = discord.Object(id=DEV_GUILD_ID)
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
            db = bot.db
            word_clean = word.strip()
            word_lower = word_clean.lower()
            existing = await db.words.find_one({"word_lower": word_lower})
            if existing:
                await interaction.followup.send(f"`{word_clean}` is already in the dictionary.")
                return
            posted_by = interaction.user.display_name
            
            # FIX: Set pose_index to None so image_generator handle the dynamic/forced randomization properly!
            image_file = await generate_card_image(
                word=word_clean, 
                definition=definition.strip(), 
                posted_by=posted_by, 
                pose_index=None
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
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.words.insert_one(doc)
            path = GENERATED_DIR / image_file
            with open(path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=f"{word_lower}.png")
            await interaction.followup.send(content=f"**{word_clean}** added!", file=file)
        except Exception as e:
            logger.error(f"❌ COMMAND ERROR: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}")

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

    @bot.tree.command(name="list", description="List all words")
    async def list_cmd(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            db = bot.db
            cursor = db.words.find({}, {"word": 1}).sort("word", 1)
            words_list = [doc["word"] for doc in await cursor.to_list(length=100)]
            if not words_list:
                await interaction.followup.send("The dictionary is empty.")
                return
            formatted_list = ", ".join(f"`{w}`" for w in words_list)
            await interaction.followup.send(f"📚 **Dictionary Words:**\n{formatted_list[:1850]}")
        except Exception as e:
            await interaction.followup.send("Error retrieving words list.")

    @bot.tree.command(name="deleteword", description="[DEV] Force delete a word")
    async def deleteword_command(interaction: discord.Interaction, word: str):
        if interaction.user.id != DEVELOPER_USER_ID:
            await interaction.response.send_message("❌ Permission Denied.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        result = await bot.db.words.delete_one({"word": {"$regex": f"^{word.strip()}$", "$options": "i"}})
        msg = "🗑️ Deleted!" if result.deleted_count > 0 else "❓ Not found."
        await interaction.followup.send(msg, ephemeral=True)

    @bot.tree.command(name="debuglist", description="[DEV] Inspect raw DB")
    async def debuglist_command(interaction: discord.Interaction):
        if interaction.user.id != DEVELOPER_USER_ID:
            return await interaction.response.send_message("❌ Denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        docs = await bot.db.words.find().sort("_id", -1).limit(1).to_list(length=1)
        await interaction.followup.send(f"🔍 `{json.dumps(docs, default=json_util.default)}`", ephemeral=True)

    return bot

async def start_bot(token: str, db):
    global _bot
    _bot = _build_bot(db)
    await _bot.start(token)

async def stop_bot():
    global _bot, _ready
    _ready = False
    if _bot and not _bot.is_closed():
        await _bot.close()
