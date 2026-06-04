"""Cog handling automated member birthdays and server-wide seasonal holiday alerts."""
import datetime
import io
import logging
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont

from image_generator import ASSETS_DIR

logger = logging.getLogger(__name__)

class CelebrationsCog(commands.Cog):
    """Manages scheduled milestones, holiday events, and customized greeting card renders."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_check.start()

    def cog_unload(self):
        self.daily_check.cancel()

    async def generate_birthday_card(self, member: discord.Member) -> io.BytesIO:
        """Dynamically builds a custom birthday card framing the user's avatar with Meowtro."""
        # Setup a cheerful 1200x800 canvas
        canvas_size = (1200, 800)
        img = Image.new("RGB", canvas_size, color="#1A0F2B") # Dark witchy purple base
        draw = ImageDraw.Draw(img)
        
        # Draw elegant festival borders
        draw.rectangle([(20, 20), (1180, 780)], outline="#DCD0FF", width=4)
        
        # Load Meowtro Mascot Asset if it exists
        mascot_path = ASSETS_DIR / "meowtro_birthday.png"
        if mascot_path.exists():
            mascot = Image.open(mascot_path).convert("RGBA")
            mascot.thumbnail((350, 350), Image.Resampling.LANCZOS)
            img.paste(mascot, (780, 380), mascot) # Corner placement
            
        # Fetch, process, and paste the user's avatar
        avatar_bytes = await member.display_avatar.read()
        avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar_img = avatar_img.resize((250, 250), Image.Resampling.LANCZOS)
        
        # Create a circular clip mask for the avatar frame
        mask = Image.new("L", (250, 250), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 250, 250), fill=255)
        
        img.paste(avatar_img, (150, 250), mask)
        draw.ellipse((145, 245, 405, 505), outline="#DCD0FF", width=5) # Avatar frame border
        
        # Text Overlay
        try:
            font_title = ImageFont.truetype("assets/title_font.ttf", 60)
            font_sub = ImageFont.truetype("assets/body_font.ttf", 40)
        except IOError:
            font_title = font_sub = ImageFont.load_default()
            
        draw.text((150, 100), "HAPPY BIRTHDAY!", fill="#EAE6FF", font=font_title)
        draw.text((450, 320), f"{member.display_name}", fill="#DCD0FF", font=font_title)
        draw.text((450, 410), "May your day be filled with\nimmaculate energy and maximum vibes!", fill="#BFA3FF", font=font_sub)
        
        # Save out to an in-memory buffer stream
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @tasks.loop(hours=24)
    async def daily_check(self):
        """Runs once a day to check for active birthdays and major seasonal holiday milestones."""
        db = self.bot.db
        now = datetime.datetime.now()
        current_md = now.strftime("%m-%d") # Format: MM-DD
        
        # Locate celebration output destination mapping channel
        config = await db.settings.find_one({"setting_id": "celebration_config"})
        if not config or not config.get("channel_id"):
            return
            
        channel = self.bot.get_channel(int(config["channel_id"]))
        if not channel:
            return

        # --- PART 1: PROCESS BIRTHDAYS ---
        # Query all members matching today's month and day
        cursor = db.users.find({"birthday": current_md})
        async for user_doc in cursor:
            guild = channel.guild
            member = guild.get_member(int(user_doc["user_id"]))
            
            if member:
                # Build their customized avatar card
                card_buffer = await self.generate_birthday_card(member)
                file = discord.File(card_buffer, filename="happy_birthday.png")
                
                # Posting standard balloon strings often triggers native mobile animations!
                msg = f"🎈🎉 **CELEBRATION TIME!** 🎉🎈\nWishing a massive Happy Birthday to {member.mention}! 🎈✨"
                await channel.send(content=msg, file=file)

        # --- PART 2: PROCESS SEASONAL HOLIDAYS ---
        # Map calendar dates to their respective unique master artwork files
        holidays = {
            "10-31": {"name": "Spooky Season / Halloween", "file": "holiday_halloween.png", "ping": True},
            "12-25": {"name": "Midwinter / Festive Season", "file": "holiday_festive.png", "ping": True},
            "06-21": {"name": "Summer Solstice", "file": "holiday_solstice.png", "ping": False}
        }
        
        if current_md in holidays:
            event = holidays[current_md]
            path = ASSETS_DIR / "tarot_deck" / event["file"]
            
            if path.exists():
                with open(path, "rb") as f:
                    file = discord.File(io.BytesIO(f.read()), filename=event["file"])
                
                ping_prefix = "@everyone " if event["ping"] else ""
                announce_text = f"✨ 🏰 **{event['name'].upper()}** 🏰 ✨\n{ping_prefix}Meowtro wishes the entire community a wonderful, cozy day!"
                await channel.send(content=announce_text, file=file)

    @daily_check.before_loop
    async def before_daily_starts(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="set_birthday", description="Register your birthday with the server oracle so we can celebrate you!")
    async def set_birthday_cmd(self, interaction: discord.Interaction, month: int, day: int):
        await interaction.response.defer(ephemeral=True)
        
        if not (1 <= month <= 12) or not (1 <= day <= 31):
            await interaction.followup.send("❌ Please enter a valid calendar date format (Month: 1-12, Day: 1-31).", ephemeral=True)
            return
            
        formatted_date = f"{month:02d}-{day:02d}"
        db = self.bot.db
        
        await db.users.update_one(
            {"user_id": str(interaction.user.id)},
            {"$set": {"birthday": formatted_date}},
            upsert=True
        )
        await interaction.followup.send(f"🎂 Success! Your birthday has been saved as **{formatted_date}**. Look out for Meowtro's custom card when your day arrives!", ephemeral=True)

    @app_commands.command(name="set_celebration_channel", description="[ADMIN] Set where birthday cards and seasonal holidays get announced.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_channel_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        await db.settings.update_one(
            {"setting_id": "celebration_config"},
            {"$set": {"channel_id": str(channel.id)}},
            upsert=True
        )
        await interaction.followup.send(f"🎯 Celebration updates linked to {channel.mention} successfully.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CelebrationsCog(bot))
