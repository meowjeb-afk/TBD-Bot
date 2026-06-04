"""Cog bundling server economy, quote memory banks, and asynchronous task reminders."""
import asyncio
import logging
import random
import time
import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

class UtilitiesCog(commands.Cog):
    """Manages community progression tokens, quote preservation, and scheduler triggers."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_scheduler.start()

    def cog_unload(self):
        self.reminder_scheduler.cancel()

    # --- PART 1: THE SERVER ECONOMY (CATNIP TOKENS) ---
    async def adjust_balance(self, user_id: str, amount: int) -> int:
        """Helper function to cleanly adjust a user's currency pool in MongoDB."""
        db = self.bot.db
        result = await db.users.find_and_modify(
            query={"user_id": user_id},
            update={"$inc": {"catnip_tokens": amount}},
            upsert=True,
            new=True
        )
        return result.get("catnip_tokens", 0)

    @app_commands.command(name="wallet", description="Check your current Catnip Token balance.")
    async def wallet_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = self.bot.db
        doc = await db.users.find_one({"user_id": str(interaction.user.id)})
        balance = doc.get("catnip_tokens", 0) if doc else 0
        
        embed = discord.Embed(
            title="🪙 Your Vault Balance",
            description=f"You currently possess **{balance}** Catnip Tokens.\nKeep active in chat to automatically generate more wealth!",
            color=discord.Color.from_str("#DCD0FF")
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="shop", description="Spend your hard-earned tokens on server rewards and pet supplies!")
    async def shop_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="🎪 The Meowtro Souvenir Shop",
            description="Use `/buy [item_id]` to exchange your tokens for rare treats!",
            color=discord.Color.from_str("#4A3B63")
        )
        embed.add_field(name="📦 `1` - Premium Fish Feast (Cost: 50 Tokens)", value="Restores **+40 Hunger** to Meowtro via the Virtual Pet system.", inline=False)
        embed.add_field(name="🔮 `2` - Shiny Star Sticker (Cost: 100 Tokens)", value="A purely cosmetic vanity role badge showing your elite status.", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="buy", description="Purchase an item from the server token shop.")
    async def buy_cmd(self, interaction: discord.Interaction, item_id: int):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        user_id = str(interaction.user.id)
        
        doc = await db.users.find_one({"user_id": user_id})
        balance = doc.get("catnip_tokens", 0) if doc else 0
        
        if item_id == 1:
            if balance < 50:
                await interaction.followup.send("❌ You don't have enough tokens for a Fish Feast! Cost is 50.")
                return
            await self.adjust_balance(user_id, -50)
            # CROSSOVER ACTION: Add the food item straight into the virtual pet inventory!
            await db.virtual_pet.update_one(
                {"pet_id": "server_mascot"},
                {"$inc": {"inventory.fish_feast": 1}},
                upsert=True
            )
            await interaction.followup.send("🎉 Purchase successful! A Premium Fish Feast has been added to Meowtro's inventory. Use `/petstatus` to feed it to them!")
            
        elif item_id == 2:
            if balance < 100:
                await interaction.followup.send("❌ You don't have enough tokens for this sticker badge! Cost is 100.")
                return
            await self.adjust_balance(user_id, -100)
            await interaction.followup.send("🎉 You bought the Shiny Star Sticker! (An admin can now manually assign your premium sticker role badge).")
        else:
            await interaction.followup.send("❌ Invalid item ID. Check `/shop` for valid options.")

    # --- PART 2: THE INTERACTIVE QUOTE SYSTEM ---
    @app_commands.command(name="quote_add", description="Save a legendary, out-of-context quote into server history.")
    async def quote_add_cmd(self, interaction: discord.Interaction, member: discord.Member, quote: str):
        await interaction.response.defer()
        db = self.bot.db
        
        quote_doc = {
            "speaker_id": str(member.id),
            "speaker_name": member.display_name,
            "quote_text": quote.strip(),
            "added_by": interaction.user.display_name,
            "timestamp": time.time()
        }
        await db.quotes.insert_one(quote_doc)
        
        embed = discord.Embed(
            title="📝 Quote Archived",
            description=f'*" {quote} "*\n— **{member.display_name}**',
            color=discord.Color.from_str("#DCD0FF")
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quote", description="Pull a completely random piece of out-of-context server history.")
    async def quote_random_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = self.bot.db
        
        count = await db.quotes.count_documents({})
        if count == 0:
            await interaction.followup.send("The quote archive is currently empty! Use `/quote_add` to log some chaos.")
            return
            
        random_index = random.randint(0, count - 1)
        cursor = db.quotes.find({}).skip(random_index).limit(1)
        docs = await cursor.to_list(length=1)
        quote_data = docs[0]
        
        embed = discord.Embed(
            title="🔮 Out of Context Wisdom",
            description=f'### *"{quote_data["quote_text"]}"*\n\n— **{quote_data["speaker_name"]}**',
            color=discord.Color.from_str("#4A3B63")
        )
        embed.set_footer(text=f"Archived by {quote_data['added_by']}")
        await interaction.followup.send(embed=embed)

    # --- PART 3: COZY TASK REMINDERS ---
    @app_commands.command(name="remindme", description="Set a dynamic countdown timer for accountability or tasks.")
    async def remindme_cmd(self, interaction: discord.Interaction, minutes: int, message: str):
        await interaction.response.defer(ephemeral=True)
        if minutes < 1 or minutes > 43200: # Max 30 days
            await interaction.followup.send("❌ Please enter a duration between 1 minute and 43200 minutes.")
            return
            
        db = self.bot.db
        trigger_time = time.time() + (minutes * 60)
        
        reminder_doc = {
            "user_id": str(interaction.user.id),
            "channel_id": str(interaction.channel_id),
            "message": message.strip(),
            "trigger_time": trigger_time,
            "processed": False
        }
        await db.reminders.insert_one(reminder_doc)
        await interaction.followup.send(f"⏰ Got it! I will ping you right here in **{minutes} minute(s)** to remind you: *\"{message}\"*")

    @tasks.loop(seconds=30)
    async def reminder_scheduler(self):
        """Background daemon task checking MongoDB for pending countdown expirations."""
        db = self.bot.db
        now = time.time()
        
        # Pull all unfulfilled timers that have passed their expiration windows
        cursor = db.reminders.find({"trigger_time": {"$lte": now}, "processed": False})
        async for reminder in cursor:
            channel = self.bot.get_channel(int(reminder["channel_id"]))
            user = self.bot.get_user(int(reminder["user_id"]))
            
            if channel and user:
                try:
                    await channel.send(f"⏰ **REMINDER ALERT** {user.mention}\nYou asked me to tell you: *\"{reminder['message']}\"*")
                except Exception:
                    pass # Keep looping gracefully even if text permissions fail
                    
            # Mark as processed so it isn't evaluated on the next pass
            await db.reminders.update_one({"_id": reminder["_id"]}, {"$set": {"processed": True}})

    @reminder_scheduler.before_loop
    async def before_scheduler_starts(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(UtilitiesCog(bot))
