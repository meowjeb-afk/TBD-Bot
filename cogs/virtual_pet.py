"""Cog handling the collaborative Server Virtual Pet Mascot module framework."""
import io
import logging
import time
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from image_generator import ASSETS_DIR, GENERATED_DIR, TOTAL_CAT_MASCOTS
from cogs.karma import award_catnip

logger = logging.getLogger(__name__)

class PetControlPanel(discord.ui.View):
    def __init__(self, cog, pet_data: dict = None):
        super().__init__(timeout=None)
        self.cog = cog
        self.bot = cog.bot
        
    @discord.ui.button(label="Feed (Snackies)", style=discord.ButtonStyle.success, emoji="🐟", custom_id="tbd_pet_feed")
    async def feed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        updates = {"$inc": {"hunger": 20}, "$set": {"last_interacted": time.time()}}
        await self._process_interaction(interaction, updates, "🍖 You fed the purple derp cat some snacks!")

    @discord.ui.button(label="Play (Zoomies)", style=discord.ButtonStyle.primary, emoji="🧸", custom_id="tbd_pet_play")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        updates = {"$inc": {"affection": 15, "energy": -10}, "$set": {"last_interacted": time.time()}}
        await self._process_interaction(interaction, updates, "⚡ You played with the pet! It got the zoomies!")

    @discord.ui.button(label="Pet (Scritches)", style=discord.ButtonStyle.secondary, emoji="💖", custom_id="tbd_pet_scritches")
    async def scritches_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        updates = {"$inc": {"affection": 10}, "$set": {"last_interacted": time.time()}}
        await self._process_interaction(interaction, updates, "💕 You gave the pet premium head scritches!")

    async def _process_interaction(self, interaction: discord.Interaction, updates: dict, action_text: str):
        db = self.bot.db
        pet = await db.virtual_pet.find_one_and_update(
            {"pet_id": "server_mascot"}, updates, return_document=True
        )
        
        pet["hunger"] = max(0, min(100, pet.get("hunger", 50)))
        pet["energy"] = max(0, min(100, pet.get("energy", 80)))
        pet["affection"] = max(0, min(100, pet.get("affection", 70)))
        await db.virtual_pet.replace_one({"pet_id": "server_mascot"}, pet)
        
        # Award +5 Catnip leaves to the player for being an amazing caretaker
        new_stash = await award_catnip(db, interaction.user.id, interaction.user.display_name, 5)
        
        filename = f"pet_{interaction.id}.png"
        output_path = await asyncio.to_thread(self.cog._render_pet_status_card, pet, filename)
        
        with open(output_path, "rb") as f:
            data = f.read()
        file = discord.File(io.BytesIO(data), filename=filename)
        
        complete_msg = f"**Status Update:** {action_text} 🌿 *(You earned 5 Catnip! Total: {new_stash})*"
        await interaction.message.edit(content=complete_msg, attachments=[file], view=self)


class VirtualPetCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.font_title_path = ASSETS_DIR / "title_font.ttf"
        self.font_body_path = ASSETS_DIR / "body_font.ttf"

    async def _get_or_init_pet(self) -> dict:
        db = self.bot.db
        pet = await db.virtual_pet.find_one({"pet_id": "server_mascot"})
        if not pet:
            pet = {
                "pet_id": "server_mascot", "name": "The Purple Derp",
                "hunger": 60, "energy": 80, "affection": 70, "last_interacted": time.time()
            }
            await db.virtual_pet.insert_one(pet)
        return pet

    def _render_pet_status_card(self, pet: dict, filename: str) -> Path:
        canvas_size = (1800, 1100)
        img = Image.new("RGB", canvas_size, color="#1D122B")
        draw = ImageDraw.Draw(img)

        draw.rectangle([(40, 40), (1760, 1060)], outline="#2E1A47", width=10)
        draw.rectangle([(55, 55), (1745, 1045)], outline="#DCD0FF", width=2)

        try:
            font_title = ImageFont.truetype(str(self.font_title_path), 80)
            font_ui = ImageFont.truetype(str(self.font_body_path), 45)
        except Exception:
            font_title = font_ui = ImageFont.load_default()

        draw.text((100, 100), f"🐾 {pet['name'].upper()}", fill="#DCD0FF", font=font_title)

        # Dynamic pose alteration indicators
        if pet["hunger"] < 30 or pet["affection"] < 30:
            pose_idx = 1  # Moody/Grumpy state
        elif pet["energy"] < 30:
            pose_idx = 5  # Unbelievably flat/sleepy state
        else:
            pose_idx = 0  # Standard vibe stance

        cat_path = ASSETS_DIR / f"cat_{pose_idx % TOTAL_CAT_MASCOTS}.png"
        if cat_path.exists():
            cat_img = Image.open(cat_path).convert("RGBA")
            cat_img = cat_img.resize((550, 450), Image.Resampling.LANCZOS)
            img.paste(cat_img, (100, 350), cat_img)

        stat_y = 380
        stats_to_draw = [
            ("Fullness", pet["hunger"], "#FF6B6B"),
            ("Energy", pet["energy"], "#FFD93D"),
            ("Affection", pet["affection"], "#FF8AAE")
        ]

        for label, val, color_hex in stats_to_draw:
            draw.text((750, stat_y), f"{label}: {val}/100", fill="#EAE6FF", font=font_ui)
            bar_x1, bar_y1, bar_x2, bar_y2 = 750, stat_y + 65, 1600, stat_y + 105
            draw.rectangle([bar_x1, bar_y1, bar_x2, bar_y2], fill="#2E1A47", outline="#DCD0FF", width=2)
            
            if val > 0:
                fill_width = int((bar_x2 - bar_x1) * (val / 100.0))
                draw.rectangle([bar_x1 + 2, bar_y1 + 2, bar_x1 + fill_width - 2, bar_y2 - 2], fill=color_hex)
            stat_y += 180

        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", compress_level=1)
        return output_path

    @app_commands.command(name="petstatus", description="Summon the server pet dashboard interface panel.")
    async def petstatus_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            pet = await self._get_or_init_pet()
            filename = f"pet_status_{interaction.id}.png"
            output_path = await asyncio.to_thread(self._render_pet_status_card, pet, filename)
            
            with open(output_path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=filename)
            
            view = PetControlPanel(self, pet)
            await interaction.followup.send(content="🎮 **The TBD Collaborative Mascot Panel**", file=file, view=view)
        except Exception as e:
            logger.error(f"Error launching pet dashboard: {e}", exc_info=True)
            await interaction.followup.send("Failed to retrieve mascot initialization panel context.")

async def setup(bot: commands.Bot):
    await bot.add_cog(VirtualPetCog(bot))
