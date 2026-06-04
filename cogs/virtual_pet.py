"""Cog handling the collaborative Server Virtual Pet Mascot module framework."""
import io
import logging
import random
import time
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from image_generator import ASSETS_DIR, GENERATED_DIR, TOTAL_CAT_MASCOTS

logger = logging.getLogger(__name__)

class PetControlPanel(discord.ui.View):
    """Adds live interactive buttons underneath the pet card for feeding, playing, and petting."""
    def __init__(self, cog, pet_data: dict):
        super().__init__(timeout=None)
        self.cog = cog
        self.bot = cog.bot
        
    @discord.ui.button(label="Feed (Snackies)", style=discord.ButtonStyle.success, emoji="🐟", custom_id="tbd_pet_feed")
    async def feed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Cap stats securely at 100 max
        updates = {"$inc": {"hunger": 20}, "$set": {"last_interacted": time.time()}}
        await self._process_interaction(interaction, updates, "🍖 You fed the pet some crunchy snackies!")

    @discord.ui.button(label="Play (Zoomies)", style=discord.ButtonStyle.primary, emoji="🧸", custom_id="tbd_pet_play")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Playing increases affection but costs energy
        updates = {"$inc": {"affection": 15, "energy": -10}, "$set": {"last_interacted": time.time()}}
        await self._process_interaction(interaction, updates, "⚡ You played with the pet! It got the zoomies!")

    @discord.ui.button(label="Pet (Scritches)", style=discord.ButtonStyle.secondary, emoji="💖", custom_id="tbd_pet_scritches")
    async def scritches_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        updates = {"$inc": {"affection": 10}, "$set": {"last_interacted": time.time()}}
        await self._process_interaction(interaction, updates, "💕 You gave the pet premium head scritches!")

    async def _process_interaction(self, interaction: discord.Interaction, updates: dict, action_text: str):
        db = self.bot.db
        # Atomically modify global pet tracker stats, forcing bounds limits via post-processing encapsulation
        pet = await db.virtual_pet.find_one_and_update(
            {"pet_id": "server_mascot"},
            updates,
            return_document=True
        )
        
        # Enforce strict 0-100 bounds limitations on stats variables
        pet["hunger"] = max(0, min(100, pet.get("hunger", 50)))
        pet["energy"] = max(0, min(100, pet.get("energy", 80)))
        pet["affection"] = max(0, min(100, pet.get("affection", 70)))
        
        await db.virtual_pet.replace_one({"pet_id": "server_mascot"}, pet)
        
        # Render updated asset card layout dynamically
        filename = f"pet_{interaction.id}.png"
        output_path = await asyncio.to_thread(self.cog._render_pet_status_card, pet, filename)
        
        with open(output_path, "rb") as f:
            data = f.read()
        file = discord.File(io.BytesIO(data), filename=filename)
        
        # Edit the original chat display component embed panel gracefully
        await interaction.message.edit(content=f"**Status Update:** {action_text}", attachments=[file], view=self)


class VirtualPetCog(commands.Cog):
    """Manages server pet lifecycle status, text generation overlays, and background stat decay loops."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.font_title_path = ASSETS_DIR / "title_font.ttf"
        self.font_body_path = ASSETS_DIR / "body_font.ttf"

    async def _get_or_init_pet(self) -> dict:
        """Retrieves or creates the unique unified state entity inside MongoDB."""
        db = self.bot.db
        pet = await db.virtual_pet.find_one({"pet_id": "server_mascot"})
        if not pet:
            pet = {
                "pet_id": "server_mascot",
                "name": "The TBD Mascot",
                "hunger": 60,       # 100 = Full, 0 = Starving
                "energy": 80,       # 100 = Awake, 0 = Exhausted
                "affection": 70,    # 100 = Adored, 0 = Depressed
                "last_interacted": time.time()
            }
            await db.virtual_pet.insert_one(pet)
        return pet

    def _render_pet_status_card(self, pet: dict, filename: str) -> Path:
        """Draws a beautiful custom interface showcasing character states and progress healthbars."""
        canvas_size = (1800, 1100)
        # Deep gothic dark indigo canvas backing color choice
        img = Image.new("RGB", canvas_size, color="#1D122B")
        draw = ImageDraw.Draw(img)

        # Frame boundaries accent accents
        draw.rectangle([(40, 40), (1760, 1060)], outline="#2E1A47", width=10)
        draw.rectangle([(55, 55), (1745, 1045)], outline="#DCD0FF", width=2)

        try:
            font_title = ImageFont.truetype(str(self.font_title_path), 80)
            font_ui = ImageFont.truetype(str(self.font_body_path), 45)
        except Exception:
            font_title = font_ui = ImageFont.load_default()

        # Render Header text title string block elements
        draw.text((100, 100), f"🐾 {pet['name'].upper()}", fill="#DCD0FF", font=font_title)

        # Determine Mascot pose index based on current health levels dynamically
        # If low on affection or starving, pick a dramatic asset frame profile layout
        if pet["hunger"] < 30 or pet["affection"] < 30:
            pose_idx = 1  # Dramatic/Grumpy asset marker placement indices
        elif pet["energy"] < 30:
            pose_idx = 5  # Sleepy/Drowsy layout asset profile target
        else:
            pose_idx = 0  # Standard cheerful signature cat avatar stance

        cat_path = ASSETS_DIR / f"cat_{pose_idx % TOTAL_CAT_MASCOTS}.png"
        if cat_path.exists():
            cat_img = Image.open(cat_path).convert("RGBA")
            cat_img = cat_img.resize((550, 450), Image.Resampling.LANCZOS)
            img.paste(cat_img, (100, 350), cat_img)

        # Draw UI Status bars structures configuration setups
        stat_y = 380
        stats_to_draw = [
            ("Fullness", pet["hunger"], "#FF6B6B"),
            ("Energy", pet["energy"], "#FFD93D"),
            ("Affection", pet["affection"], "#FF8AAE")
        ]

        for label, val, color_hex in stats_to_draw:
            # Render descriptive label text strings elements
            draw.text((750, stat_y), f"{label}: {val}/100", fill="#EAE6FF", font=font_ui)
            
            # Progress tracker channel base container bounds mapping
            bar_x1, bar_y1, bar_x2, bar_y2 = 750, stat_y + 65, 1600, stat_y + 105
            draw.rectangle([bar_x1, bar_y1, bar_x2, bar_y2], fill="#2E1A47", outline="#DCD0FF", width=2)
            
            # Fill dynamic width tracking meter segments calculations
            if val > 0:
                fill_width = int((bar_x2 - bar_x1) * (val / 100.0))
                draw.rectangle([bar_x1 + 2, bar_y1 + 2, bar_x1 + fill_width - 2, bar_y2 - 2], fill=color_hex)
                
            stat_y += 180

        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", compress_level=1)
        return output_path

    @app_commands.command(name="petstatus", description="Summon the server pet dashboard interface panel to chat context.")
    async def petstatus_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            pet = await self._get_or_init_pet()
            filename = f"pet_status_{interaction.id}.png"
            
            # Offload synchronous background processes out of runtime stack loops
            output_path = await asyncio.to_thread(self._render_pet_status_card, pet, filename)
            
            with open(output_path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=filename)
            
            view = PetControlPanel(self, pet)
            await interaction.followup.send(content="🎮 **The TBD Collaborative Mascot Panel**", file=file, view=view)
        except Exception as e:
            logger.error(f"Error launching pet dashboard framework interface router: {e}", exc_info=True)
            await interaction.followup.send("Failed to retrieve mascot initialization panel context.")

async def setup(bot: commands.Bot):
    """Registers the Virtual Pet module context into global loader configuration loops."""
    await bot.add_cog(VirtualPetCog(bot))
