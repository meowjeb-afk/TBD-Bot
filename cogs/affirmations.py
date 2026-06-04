"""Cog handling dynamic, character-driven affirmations for server members."""
import io
import logging
import random
import time
import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from image_generator import ASSETS_DIR, GENERATED_DIR, TOTAL_CAT_MASCOTS, draw_mixed_font_text

logger = logging.getLogger(__name__)

class AffirmationsCog(commands.Cog):
    """Generates personalized positive reminders and overlays them onto stylized mascot cards."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Dedicated layout settings for affirmation cards
        self.font_title_path = ASSETS_DIR / "title_font.ttf"
        self.font_body_path = ASSETS_DIR / "body_font.ttf"
        self.font_fallback_path = ASSETS_DIR / "notosans_fallback.ttf"

    def _render_affirmation_card(self, target_name: str, message: str, pose_index: int, filename: str) -> Path:
        """Synchronous drawing canvas setup for processing an affirmation asset."""
        # Create a beautiful, soft pastel horizontal canvas from scratch
        canvas_size = (1600, 1000)
        img = Image.new("RGB", canvas_size, color="#F4EBFD") # Soft cottagecore lavender-tint tint
        draw = ImageDraw.Draw(img)

        # Draw a clean border frame asset
        draw.rectangle([(40, 40), (1560, 960)], outline="#DCD0FF", width=8)
        draw.rectangle([(50, 50), (1550, 950)], outline="#2E1A47", width=4)

        try:
            font_header = ImageFont.truetype(str(self.font_title_path), 65)
            font_msg = ImageFont.truetype(str(self.font_body_path), 45)
            font_fallback = ImageFont.truetype(str(self.font_fallback_path), 45)
        except Exception:
            font_header = font_msg = font_fallback = ImageFont.load_default()

        # 1. Header Text: "A SPECIAL REMINDER FOR..."
        header_text = f"✨ FOR {target_name.upper()} ✨"
        header_w = draw.textlength(header_text, font=font_header)
        draw.text((800 - (header_w / 2), 120), header_text, fill="#2E1A47", font=font_header)

        # 2. Main Message Body Wrapping Block
        import textwrap
        wrapped_lines = textwrap.wrap(message, width=38)
        curr_y = 320
        for line in wrapped_lines:
            line_w = draw.textlength(line, font=font_msg)
            # Center-align the text lines elegantly on the canvas
            draw.text((800 - (line_w / 2), curr_y), line, fill="#4A3B63", font=font_msg)
            curr_y += 65

        # 3. Mascot Placement Layer (Bottom Right)
        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_img = Image.open(cat_path).convert("RGBA")
            # Downscale slightly to fit the affirmation card proportions
            cat_img = cat_img.resize((400, 300), Image.Resampling.LANCZOS)
            img.paste(cat_img, (1100, 620), cat_img)

        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", compress_level=1)
        return output_path

    @app_commands.command(name="affirm", description="Send a personalized, character-driven affirmation to a server friend!")
    @app_commands.describe(
        member="The friend you want to uplift",
        style="The thematic style flavor of your affirmation card"
    )
    @app_commands.choices(style=[
        app_commands.Choice(name="Cosy (Sweet & Gentle)", value="cosy"),
        app_commands.Choice(name="Gothic (Creepy-Cute & Dark)", value="gothic"),
        app_commands.Choice(name="Chaotic (High Energy Hype)", value="chaotic")
    ])
    async def affirm_cmd(self, interaction: discord.Interaction, member: discord.Member, style: str):
        await interaction.response.defer(thinking=True)
        try:
            db = self.bot.db
            
            # Query MongoDB for a random message fitting the chosen style choice
            query = {"style": style}
            count = await db.affirmations.count_documents(query)
            
            if count > 0:
                random_index = random.randint(0, count - 1)
                cursor = db.affirmations.find(query).skip(random_index).limit(1)
                doc_list = await cursor.to_list(length=1)
                affirmation_text = doc_list[0]["text"]
            else:
                # Fun structural fallbacks if your database collection isn't seeded yet
                fallbacks = {
                    "cosy": "You are doing incredibly well. Take a deep breath and have a warm cup of tea.",
                    "gothic": "Your internal aesthetic profile is exquisite. Even the shadows are admiring you today.",
                    "chaotic": "ABSOLUTE CHAMPION DETECTED! CRUSHING TARGET METRICS EFFORTLESSLY TODAY!"
                }
                affirmation_text = fallbacks.get(style, "You're fantastic!")

            # Prepare file attributes
            filename = f"affirm_{interaction.id}.png"
            target_display = member.display_name
            
            # Select a random mascot pose
            random.seed(time.time())
            pose_index = random.randint(0, TOTAL_CAT_MASCOTS - 1)

            # Offload heavy Pillow operations safely to a worker thread
            import asyncio
            output_path = await asyncio.to_thread(
                self._render_affirmation_card, target_display, affirmation_text, pose_index, filename
            )

            # Send file stream to the active Discord text channel context
            with open(output_path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=filename)

            await interaction.followup.send(
                content=f"💖 {interaction.user.mention} sent a beautiful drop of validation over to {member.mention}!",
                file=file
            )
        except Exception as e:
            logger.error(f"❌ AFFIRMATION COG ROUTINE ERROR: {e}", exc_info=True)
            await interaction.followup.send("An error occurred trying to generate your affirmation card.")

async def setup(bot: commands.Bot):
    """Registers the Affirmations file layout into the core bot context runtime."""
    await bot.add_cog(AffirmationsCog(bot))
