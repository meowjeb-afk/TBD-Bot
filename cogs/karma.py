"""Cog handling the Catnip currency, profile balances, and server leaderboards."""
import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

async def award_catnip(db, user_id: str, display_name: str, amount: int) -> int:
    """Helper utility to safely award or deduct Catnip for a user in MongoDB."""
    try:
        result = await db.users.find_one_and_update(
            {"discord_id": str(user_id)},
            {
                "$set": {"display_name": display_name},
                "$inc": {"catnip": amount}
            },
            upsert=True,
            return_document=True
        )
        return result.get("catnip", 0) if result else 0
    except Exception as e:
        logger.error(f"Failed to award Catnip to user {user_id}: {e}")
        return 0


class KarmaCog(commands.Cog):
    """Manages the server's economy of premium Catnip leaves."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stash", description="Check how many leaves of Catnip you have hoarded in your stash.")
    async def stash_cmd(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer(thinking=True)
        db = self.bot.db
        target = member or interaction.user
        
        user_doc = await db.users.find_one({"discord_id": str(target.id)})
        balance = user_doc.get("catnip", 0) if user_doc else 0
        
        embed = discord.Embed(
            title="🌿 The Catnip Stash",
            description=f"{target.mention} has hoarded **{balance}** leaves of premium Catnip!",
            color=discord.Color.from_str("#DCD0FF")
        )
        
        if balance == 0:
            status = "Completely sober. The fat purple cat ignores them entirely."
        elif balance < 50:
            status = "A modest pile. The purple derp cat is starting to look their way."
        else:
            status = "An absolute kingpin. The mascot is actively vibrating in their presence."
            
        embed.set_footer(text=f"Status: {status}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="leaderboard", description="See who holds the biggest Catnip monopoly in the server.")
    async def leaderboard_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        db = self.bot.db
        
        cursor = db.users.find({"catnip": {"$gt": 0}}).sort("catnip", -1).limit(10)
        top_users = await cursor.to_list(length=10)
        
        if not top_users:
            await interaction.followup.send("Nobody has hoarded any Catnip yet! Start interacting to earn some.")
            return

        leaderboard_text = []
        medals = ["🥇", "🥈", "🥉"]
        
        for index, doc in enumerate(top_users):
            prefix = medals[index] if index < 3 else f"`#{index + 1}`"
            leaderboard_text.append(f"{prefix} **{doc['display_name']}** — {doc['catnip']} 🌿")

        embed = discord.Embed(
            title="🔮 The Great Catnip Monopoly",
            description="\n".join(leaderboard_text),
            color=discord.Color.from_str("#4A3B63")
        )
        embed.set_footer(text="Keep contributing to become the ultimate Catnip Dealer.")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(KarmaCog(bot))
