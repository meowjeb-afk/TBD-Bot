"""Cog handling dynamic, character-driven affirmations for server members."""
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

class AffirmationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.font_title_path = ASSETS_DIR / "title_font.ttf"
        self.font_body_path = ASSETS_DIR / "body_font.ttf"
        self.font_fallback_path = ASSETS_DIR / "notosans_fallback.ttf"

    def _render_affirmation_card(self, target_name: str, message: str, pose_index: int, filename: str) -> Path:
        canvas_size = (1600, 1000)
        img = Image.new("RGB", canvas_size, color="#F4EBFD")
        draw = ImageDraw.Draw(img)

        draw.rectangle([(40, 40), (1560, 960)], outline="#DCD0FF", width=8)
        draw.rectangle([(50, 50), (1550, 950)], outline="#2E1A47", width=4)

        try:
            font_header = ImageFont.truetype(str(self.font_title_path), 65)
            font_msg = ImageFont.truetype(str(self.font_body_path), 45)
        except Exception:
            font_header = font_msg = ImageFont.load_default()

        header_text = f"✨ FOR {target_name.upper()} ✨"
        header_w = draw.textlength(header_text, font=font_header)
        draw.text((800 - (header_w / 2), 120), header_text, fill="#2E1A47", font=font_header)

        wrapped_lines = textwrap.wrap(message, width=38)
        curr_y = 320
        for line in wrapped_lines:
            line_w = draw.textlength(line, font=font_msg)
            draw.text((800 - (line_w / 2), curr_y), line, fill="#4A3B63", font=font_msg)
            curr_y += 65

        cat_num = pose_index % TOTAL_CAT_MASCOTS
        cat_path = ASSETS_DIR / f"cat_{cat_num}.png"
        if cat_path.exists():
            cat_img = Image.open(cat_path).convert("RGBA")
            cat_img = cat_img.resize((400, 300), Image.Resampling.LANCZOS)
            img.paste(cat_img, (1100, 620), cat_img)

        output_path = GENERATED_DIR / filename
        img.save(output_path, "PNG", compress_level=1)
        return output_path

    @app_commands.command(name="affirm", description="Send a personalized affirmation card to a server friend!")
    @app_commands.choices(style=[
        app_commands.Choice(name="Cosy (Sweet & Gentle)", value="cosy"),
        app_commands.Choice(name="Gothic (Creepy-Cute & Dark)", value="gothic"),
        app_commands.Choice(name="Chaotic (High Energy Hype)", value="chaotic")
    ])
    async def affirm_cmd(self, interaction: discord.Interaction, member: discord.Member, style: str):
        await interaction.response.defer(thinking=True)
        try:
            db = self.bot.db
            cursor = db.affirmations.find({"style": style})
            count = await db.affirmations.count_documents({"style": style})
            
            if count > 0:
                random_index = random.randint(0, count - 1)
                doc_list = await db.affirmations.find({"style": style}).skip(random_index).limit(1).to_list(length=1)
                affirmation_text = doc_list[0]["text"]
            else:
                fallbacks = {
                    "cosy": "You are doing incredibly well. Take a deep breath.",
                    "gothic": "Your internal aesthetic profile is exquisite. Even the shadows are admiring you.",
                    "chaotic": "ABSOLUTE CHAMPION DETECTED! CRUSHING TARGET METRICS EFFORTLESSLY!"
                }
                affirmation_text = fallbacks.get(style, "You're fantastic!")

            filename = f"affirm_{interaction.id}.png"
            target_display = member.display_name
            
            random.seed(time.time())
            pose_index = random.randint(0, TOTAL_CAT_MASCOTS - 1)

            output_path = await asyncio.to_thread(
                self._render_affirmation_card, target_display, affirmation_text, pose_index, filename
            )

            with open(output_path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=filename)

            await interaction.followup.send(
                content=f"💖 {interaction.user.mention} sent some validation over to {member.mention}!", file=file
            )
        except Exception as e:
            logger.error(f"❌ AFFIRMATION ERROR: {e}", exc_info=True)
            await interaction.followup.send("An error occurred trying to generate your affirmation card.")

async def setup(bot: commands.Bot):
    await bot.add_cog(AffirmationsCog(bot))
