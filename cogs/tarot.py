"""Cog handling the custom Inside Joke Tarot and Oracle Deck module."""
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
import textwrap

from image_generator import ASSETS_DIR, GENERATED_DIR, TOTAL_CAT_MASCOTS

logger = logging.getLogger(__name__)

# A built-in deck framework matching server themes and inside joke profiles
TAROT_DECK = {
    0: {
        "name": "THE FOOL",
        "mascot_index": 1,  # Grumpy/clumsy cat asset
        "meaning": "A reckless journey begins. Watch out for rogue lines of code, broken dependencies, and uncompiled dreams. Mind your step."
    },
    1: {
        "name": "THE MAGICIAN",
        "mascot_index": 0,  # Standard signature cat
        "meaning": "You possess all the tools required to manifest perfection. The canvas is yours, the code is clean, and success is within grasp."
    },
    10: {
        "name": "WHEEL OF FORTUNE",
        "mascot_index": 3,
        "meaning": "The server vibes shift rapidly. Chaos and clarity spin on a continuous axis. Upvotes or downvotes, the wheel turns for everyone."
    },
    13: {
        "name": "DEATH (REBORN)",
        "mascot_index": 2,  # A dramatic, creepy-cute skull/gothic vibe
        "meaning": "The ultimate end of a failed gaming run. Do not mourn the wipe; a glorious respawn and a completely fresh build await you."
    },
    16: {
        "name": "THE TOWER",
        "mascot_index": 4,
        "meaning": "Sudden, cataclysmic disruption. Someone accidentally crashed the production bot instance or a massive inside joke has broken the main chat channel."
    },
    19: {
        "name": "THE SUN",
        "mascot_index": 7,  # Sparkly/mossy cottagecore asset
        "meaning": "Immaculate energy is radiant here. Success, warmth, and validation flood your path. The ghosts are thoroughly impressed."
    }
}

class TarotCog(commands.Cog):
    """Generates random vertical Tarot card draws with overlaid inside-joke meanings."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.font_title_path = ASSETS_DIR / "title_font.ttf"
        self.font_body_path = ASSETS_DIR / "body_font.ttf"

    def _render_tarot_card(self, card_name: str, meaning: str, pose_index: int, filename: str) -> Path:
        """Synchronously draws a vertical tarot card layout with crisp canvas boundaries."""
        canvas_size = (1000, 1600)
        # Deep, mysterious midnight gothic velvet background color choice
        img = Image.new("RGB", canvas_size, color="#0F091A")
        draw = ImageDraw.Draw(img)

        # Draw traditional intricate double borders
        draw.rectangle([(30, 30), (970, 1570)], outline="#2E1A47", width=6)
        draw.rectangle([(45, 45), (955, 1555)], outline="#DCD0FF", width=3)

        try:
            font_card_title = ImageFont.truetype(str(self.font_title_path), 65)
            font_meaning = ImageFont.truetype(str(self.font_body_path), 38)
        except Exception:
            font_card_title = font_meaning = ImageFont.load_default()

        # 1. Top Card Label Title Heading
        title_w = draw.textlength(card_name, font=font_card_title)
        draw.text((500 - (title_w / 2), 90), card_name, fill="#DCD0FF", font=font_card_title)

        # 2. Main Mascot Art Framing Block (Centered Core)
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        
        # Draw a framing window box for the artwork asset
        frame_box = [(150, 220), (850, 920)]
        draw.rectangle(frame_box, fill="#1A1126", outline="#2E1A47", width=4)
        
        if cat_path.exists():
            cat_img = Image.open(cat_path).convert("RGBA")
            # Downscale dynamically to fit inside the tarot card framing container dimensions
            cat_img = cat_img.resize((550, 450), Image.Resampling.LANCZOS)
            # Center the mascot asset inside our box framework layer coordinates
            img.paste(cat_img, (225, 340), cat_img)

        # 3. Dynamic Text Block Interpretation Layout (Bottom Panel)
        wrapped_text = textwrap.wrap(meaning, width=38)
        curr_y = 1000
        
        # Inner text frame decorative accent lines block elements
        draw.line([(200, 970), (800, 970)], fill="#2E1A47", width=2)
        
        for line in wrapped_text:
            line_w = draw.textlength(line, font=font_meaning)
            draw.text((500 - (line_w / 2), curr_y), line, fill="#EAE6FF", font=font_meaning)
            curr_y += 55

        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", compress_level=1)
        return output_path

    @app_commands.command(name="tarot", description="Consult the server oracle! Draw a tarot card to answer your questions.")
    @app_commands.describe(question="The burning inquiry you wish to seek guidance on from the deck.")
    async def tarot_cmd(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)
        try:
            # Randomly select a card profile definition from our collection
            random.seed(time.time())
            card_id = random.choice(list(TAROT_DECK.keys()))
            card_data = TAROT_DECK[card_id]
            
            filename = f"tarot_{interaction.id}.png"
            
            # Run heavy drawing actions in thread loops to avoid blocking the client connection
            output_path = await asyncio.to_thread(
                self._render_tarot_card, 
                card_data["name"], 
                card_data["meaning"], 
                card_data["mascot_index"], 
                filename
            )
            
            with open(output_path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=filename)
            
            # Format clean block styling to display their prompt inquiry alongside the drawing result
            user_query = question.strip()
            if len(user_query) > 250:
                user_query = user_query[:247] + "..."
                
            response_msg = (
                f"🔮 **Tarot Reading for {interaction.user.mention}**\n"
                f"❓ *Inquiry:* \"{user_query}\"\n"
                f"✨ *The cosmic tides have drawn...*"
            )
            
            await interaction.followup.send(content=response_msg, file=file)
        except Exception as e:
            logger.error(f"❌ TAROT ENGINE ROUTINE HITCH: {e}", exc_info=True)
            await interaction.followup.send("The cosmic deck was dropped! Failed to complete your reading sample.")

async def setup(bot: commands.Bot):
    """Hooks up the Tarot module extension to the main bot context framework."""
    await bot.add_cog(TarotCog(bot))
