"""Cog handling all TBD Dictionary slash commands and interactive views."""
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from bson import json_util

# Share the same image generator engine across files
from image_generator import generate_card_image, GENERATED_DIR

logger = logging.getLogger(__name__)
DEVELOPER_USER_ID = 552956853147926532


async def word_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Dynamically queries MongoDB to offer instant drop-down suggestions as the user types."""
    try:
        # Pull the database connection out of the cog's bot client references
        db = interaction.client.db if hasattr(interaction.client, "db") else None
        if not db:
            return []
            
        if not current:
            # If nothing typed yet, return the 25 most recent additions as a helpful shortcut
            cursor = db.words.find({}, {"word": 1}).sort("_id", -1).limit(25)
            return [app_commands.Choice(name=doc["word"], value=doc["word"]) for doc in await cursor.to_list(length=25)]

        # Case-insensitive prefix match against active database records
        cursor = db.words.find({"word_lower": {"$regex": f"^{current.lower()}"}}, {"word": 1}).limit(25)
        return [app_commands.Choice(name=doc["word"], value=doc["word"]) for doc in await cursor.to_list(length=25)]
    except Exception as e:
        logger.error(f"Autocomplete engine error: {e}")
        return []


class CardInteractionView(discord.ui.View):
    """Adds persistent clickable Uppies and Share buttons underneath card layouts."""
    def __init__(self, bot: commands.Bot, word_lower: str, initial_upvotes: int = 0):
        super().__init__(timeout=None)
        self.bot = bot
        self.word_lower = word_lower
        
        if initial_upvotes > 0:
            self.uppies_button.label = f"Uppies ({initial_upvotes})"

    @discord.ui.button(label="Uppies", style=discord.ButtonStyle.primary, emoji="🔺", custom_id="tbd_uppies_btn")
    async def uppies_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            db = self.bot.db
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
            doc = await db.words.find_one({"
