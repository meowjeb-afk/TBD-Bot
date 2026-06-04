"""Cog handling the custom Inside Joke Tarot and Oracle Deck module using high-fidelity assets."""
import io
import logging
import random
import time
import discord
from discord import app_commands
from discord.ext import commands

from image_generator import ASSETS_DIR

logger = logging.getLogger(__name__)

class TarotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="tarot", description="Consult the server oracle! Draw a beautifully illustrated inside-joke card.")
    async def tarot_cmd(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)
        try:
            db = self.bot.db
            
            # 1. CROSSOVER CHECK: Query the current stats of the virtual pet mascot
            pet = await db.virtual_pet.find_one({"pet_id": "server_mascot"})
            
            # If the purple mascot is starving, override the pull with a unique cursed asset
            if pet and pet.get("hunger", 50) < 30:
                card_name = "THE HUNGRY BEAST (CURSED)"
                meaning = "The mascot is starving. The oracle refuses to answer until someone feeds it via /petstatus."
                image_file = "the_hungry_beast_cursed.png" 
            else:
                # Query your custom collection of unique tarot cards from MongoDB
                count = await db.tarot_deck.count_documents({})
                if count == 0:
                    await interaction.followup.send("The oracle deck hasn't been populated in the database yet!")
                    return
                
                # Seed and select a random card document from the collection
                random.seed(time.time())
                random_index = random.randint(0, count - 1)
                card_doc = await db.tarot_deck.find({}).skip(random_index).limit(1).to_list(length=1)
                card_data = card_doc[0]
                
                card_name = card_data["name"]
                meaning = card_data["meaning"]
                image_file = card_data["image_filename"]

            # 2. Grab the unique card file from your subfolder
            # Every card looks completely different because it's a dedicated master illustration!
            path = ASSETS_DIR / "tarot_deck" / image_file
            
            if path.exists():
                with open(path, "rb") as f:
                    data = f.read()
                file = discord.File(io.BytesIO(data), filename=image_file)
                
                # Sanitize and truncate the user question if necessary
                user_query = question.strip()
                if len(user_query) > 250: 
                    user_query = user_query[:247] + "..."
                
                response_msg = (
                    f"🔮 **Tarot Reading for {interaction.user.mention}**\n"
                    f"❓ *Inquiry:* \"{user_query}\"\n"
                    f"✨ *The cosmic tides reveal...*"
                )
                
                # Send the gorgeous card layout directly to the channel
                await interaction.followup.send(content=response_msg, file=file)
            else:
                # Safe fallback just in case an asset file is missing during development
                logger.warning(f"Tarot image asset missing at path: {path}")
                await interaction.followup.send(
                    content=f"🔮 **Tarot Reading for {interaction.user.mention}**\n"
                            f"❓ *Inquiry:* \"{question}\"\n\n"
                            f"**{card_name}**\n_{meaning}_"
                )
                
        except Exception as e:
            logger.error(f"❌ TAROT ENGINE ERROR: {e}", exc_info=True)
            await interaction.followup.send("The cosmic deck was dropped! Failed to complete your reading.")

async def setup(bot: commands.Bot):
    await bot.add_cog(TarotCog(bot))
