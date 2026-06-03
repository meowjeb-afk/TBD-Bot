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

# Aggressively silence all core discord startup warnings (voice/privileged intents)
logging.getLogger("discord").setLevel(logging.ERROR)
logging.getLogger("discord.client").setLevel(logging.ERROR)
logging.getLogger("discord.ext.commands.bot").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

DEVELOPER_USER_ID = 552956853147926532 
_bot: commands.Bot | None = None
_ready = False

def is_running() -> bool:
    return _ready and _bot is not None and not _bot.is_closed()


class CardInteractionView(discord.ui.View):
    """Adds persistent clickable Uppies and Share buttons underneath card layouts."""
    def __init__(self, bot: commands.Bot, word_lower: str, initial_upvotes: int = 0):
        super().__init__(timeout=None)
        self.bot = bot
        self.word_lower = word_lower
        
        # Dynamically set initial counter text label on load initialization
        if initial_upvotes > 0:
            self.uppies_button.label = f"Uppies ({initial_upvotes})"

    @discord.ui.button(label="Uppies", style=discord.ButtonStyle.primary, emoji="🔺", custom_id="tbd_uppies_btn")
    async def uppies_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            db = self.bot.db
            
            # Atomically increment upvote records inside MongoDB context
            result = await db.words.find_one_and_update(
                {"word_lower": self.word_lower},
                {"$inc": {"upvotes": 1}},
                return_document=True
            )
            
            if result:
                new_total = result.get("upvotes", 0)
                button.label = f"Uppies ({new_total})"
                await interaction.message.edit(view=self)
                await interaction.followup.send(f"✨ You gave Uppies to **{result['word']}**! Total: {new_total}", ephemeral=True)
            else:
                await interaction.followup.send("Could not locate this word inside the database.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error handling Uppies panel interaction: {e}")
            await interaction.followup.send("Failed to log score.", ephemeral=True)

    @discord.ui.button(label="Share", style=discord.ButtonStyle.secondary, emoji="🔗", custom_id="tbd_share_btn")
    async def share_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=False, ephemeral=True)
        try:
            db = self.bot.db
            doc = await db.words.find_one({"word_lower": self.word_lower})
            
            if doc and doc.get("github_url"):
                await interaction.followup.send(f"📥 Permanent asset link:\n`{doc['github_url']}`", ephemeral=True)
            elif doc:
                await interaction.followup.send(
                    f"📢 **{doc['word']}**:\n_{doc['definition']}_\n\n*(To share the card outside Discord, right-click the file or save the image!)*", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send("Word schema data missing.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error handling Share channel logic: {e}")
            await interaction.followup.send("Failed to compile share URL link tracking data.", ephemeral=True)


def _build_bot(db) -> commands.Bot:
    intents = discord.Intents.default()
    intents.voice_states = False  
    intents.message_content = False
    
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
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
        # Attach listener to global scope for persistent channel tracking
        bot.add_view(CardInteractionView(bot, ""))
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
                await interaction.followup.send(f"`{word_clean}` is already in the dictionary. Try using `/edit` instead!")
                return
            posted_by = interaction.user.display_name
            
            # Fetch both generated parameters safely 
            image_file, github_url = await generate_card_image(
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
                "github_url": github_url,
                "upvotes": 0, 
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.words.insert_one(doc)
            
            path = GENERATED_DIR / image_file
            with open(path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=f"{word_lower}.png")
            
            view = CardInteractionView(bot, word_lower, initial_upvotes=0)
            await interaction.followup.send(content=f"**{word_clean}** added!", file=file, view=view)
        except Exception as e:
            logger.error(f"❌ COMMAND ERROR: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}")

    @bot.tree.command(name="edit", description="Edit the definition of an existing dictionary word")
    async def edit_cmd(interaction: discord.Interaction, word: str, new_definition: str):
        await interaction.response.defer(thinking=True)
        try:
            db = bot.db
            word_clean = word.strip()
            word_lower = word_clean.lower()
            
            doc = await db.words.find_one({"word_lower": word_lower})
            if not doc:
                await interaction.followup.send(f"`{word_clean}` was not found in the dictionary.")
                return
                
            # Authorization evaluation block
            is_author = str(interaction.user.id) == doc.get("discord_user_id")
            is_admin = interaction.user.guild_permissions.administrator if interaction.guild else False
            
            if not (is_author or is_admin):
                await interaction.followup.send("⛔ Permission Denied. Only the original creator or a server administrator can modify this entry.")
                return

            posted_by = doc.get("posted_by", interaction.user.display_name)
            pose_index = len(doc.get("id", "1"))
            
            new_image_file, new_github_url = await generate_card_image(
                word=doc["word"], 
                definition=new_definition.strip(), 
                posted_by=posted_by, 
                pose_index=pose_index
            )
            
            await db.words.update_one(
                {"word_lower": word_lower},
                {
                    "$set": {
                        "definition": new_definition.strip(),
                        "image_file": new_image_file,
                        "github_url": new_github_url,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            path = GENERATED_DIR / new_image_file
            with open(path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=f"{word_lower}_edited.png")
            
            view = CardInteractionView(bot, word_lower, initial_upvotes=doc.get("upvotes", 0))
            await interaction.followup.send(
                content=f"📝 **{doc['word']}** entry details modified successfully!", 
                file=file, 
                view=view
            )
        except Exception as e:
            logger.error(f"❌ EDIT ROUTINE ERROR: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred while altering entry data: {e}")

    @bot.tree.command(name="lookup", description="Look up a word")
    async def lookup_cmd(interaction: discord.Interaction, word: str):
        await interaction.response.defer(thinking=True)
        try:
            db = bot.db
            word_lower = word.strip().lower()
            doc = await db.words.find_one({"word_lower": word_lower})
            if not doc:
                await interaction.followup.send(f"`{word}` not found.")
                return
            path = GENERATED_DIR / doc["image_file"] if doc.get("image_file") else None
            
            view = CardInteractionView(bot, word_lower, initial_upvotes=doc.get("upvotes", 0))
            if path and path.exists():
                with open(path, "rb") as f:
                    data = f.read()
                file = discord.File(io.BytesIO(data), filename=f"{doc['word_lower']}.png")
                await interaction.followup.send(content=f"**{doc['word']}**", file=file, view=view)
            else:
                await interaction.followup.send(content=f"**{doc['word']}** — {doc['definition']}", view=view)
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
