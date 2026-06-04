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


async def word_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Dynamically queries MongoDB to offer instant drop-down suggestions as the user types."""
    try:
        # Access the database attached to the bot client
        db = interaction.client.db if hasattr(interaction.client, "db") else None
        if not db or not current:
            # If nothing typed yet, grab the 25 most recent words as a fallback shortcut
            cursor = db.words.find({}, {"word": 1}).sort("_id", -1).limit(25) if db else None
            if cursor:
                return [app_commands.Choice(name=doc["word"], value=doc["word"]) for doc in await cursor.to_list(length=25)]
            return []

        # Case-insensitive prefix match against what they are currently typing
        cursor = db.words.find({"word_lower": {"$regex": f"^{current.lower()}"}}, {"word": 1}).limit(25)
        choices = [app_commands.Choice(name=doc["word"], value=doc["word"]) for doc in await cursor.to_list(length=25)]
        return choices
    except Exception as e:
        logger.error(f"Autocomplete error: {e}")
        return []


class CardInteractionView(discord.ui.View):
    """Adds persistent clickable Uppies and Share buttons underneath card layouts."""
    def __init__(self, bot: commands.Bot, word_lower: str, initial_upvotes: int = 0):
        super().__init__(timeout=None)
        self.bot = bot
        self.word_lower = word_lower
        
        # POLISH: Initialize the label to show the live database score immediately on load!
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
                button.
