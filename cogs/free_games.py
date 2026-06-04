"""Cog that periodically checks for 100% free games on Epic, Steam, GOG, and lists them."""
import logging
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

class FreeGamesCog(commands.Cog):
    """Periodically queries and displays 100% free game promotions across PC stores."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Start the background checker task loop automatically
        self.check_free_games.start()

    def cog_unload(self):
        self.check_free_games.cancel()

    async def fetch_epic_freebies(self) -> list[dict]:
        """Fetches current 100% free games from the Epic Games Store public API."""
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=en-US&country=GB&allowCountries=GB"
        games = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    
                    elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
                    for item in elements:
                        title = item.get("title")
                        # Look for active 100% off promotions
                        promotions = item.get("promotions")
                        if not promotions:
                            continue
                            
                        active_promos = promotions.get("promotionalOffers", [])
                        for promo in active_promos:
                            offers = promo.get("promotionalOffers", [])
                            for offer in offers:
                                # DiscountSetting 0 with zero value usually indicates a 100% price cut
                                if offer.get("discountSetting", {}).get("discountType") == "PERCENTAGE" and offer.get("discountSetting", {}).get("discountValue") == 0:
                                    
                                    # Snag an image thumbnail if available
                                    thumbnail = None
                                    for img in item.get("keyImages", []):
                                        if img.get("type") in ["Thumbnail", "DieselStoreFrontWide"]:
                                            thumbnail = img.get("url")
                                            break
                                            
                                    games.append({
                                        "title": title,
                                        "store": "Epic Games Store",
                                        "url": f"https://store.epicgames.com/p/{item.get('catalogNs', {}).get('mappings', [{}])[0].get('pageSlug', '')}",
                                        "thumbnail": thumbnail,
                                        "price": "FREE"
                                    })
        except Exception as e:
            logger.error(f"Error fetching Epic Games promotions: {e}")
        return games

    async def fetch_itad_freebies(self) -> list[dict]:
        """Fallback wrapper to scour generalized 100% off sales using IsThereAnyDeal feeds or open aggregates."""
        # Note: True ITAD v2 endpoints require an API key. This acts as a clean structural placeholder 
        # or can be hooked into open feeds like CheapShark's free game listings!
        games = []
        try:
            url = "https://www.cheapshark.com/api/1.0/deals?storeID=1,7&upperPrice=0" # Store 1=Steam, 7=GOG, Price 0=Free
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        deals = await resp.json()
                        for deal in deals:
                            games.append({
                                "title": deal.get("title"),
                                "store": "Steam" if deal.get("storeID") == "1" else "GOG",
                                "url": f"https://www.cheapshark.com/redirect?dealID={deal.get('dealID')}",
                                "thumbnail": deal.get("thumb"),
                                "price": "FREE"
                            })
        except Exception as e:
            logger.error(f"Error querying aggregate freebie database endpoints: {e}")
        return games

    @tasks.loop(hours=12)
    async def check_free_games(self):
        """Background loop task that automatically scans and posts new deals."""
        db = self.bot.db
        
        # Pull configuration map to find where to drop notifications
        config = await db.settings.find_one({"setting_id": "free_games_config"})
        if not config or not config.get("channel_id"):
            return # Channel isn't linked yet, skip processing loops smoothly
            
        channel = self.bot.get_channel(int(config["channel_id"]))
        if not channel:
            return

        epic_deals = await self.fetch_epic_freebies()
        agg_deals = await self.fetch_itad_freebies()
        all_deals = epic_deals + agg_deals

        for game in all_deals:
            # Prevent double posting! Check if we've already logged this game in MongoDB recently
            clean_title = game["title"].strip().lower()
            already_posted = await db.posted_freebies.find_one({"title_key": clean_title})
            
            if not already_posted:
                # Build an elegant, high-contrast store card announcement embed
                embed = discord.Embed(
                    title=f"🎁 FREE GAME: {game['title']}",
                    description=f"Grab it right now for 100% off on the **{game['store']}**!",
                    color=discord.Color.from_str("#DCD0FF")
                )
                embed.add_field(name="Link to Claim", value=f"[Click Here to Secure Deal]({game['url']})", inline=False)
                if game.get("thumbnail"):
                    embed.set_image(url=game["thumbnail"])
                    
                embed.set_footer(text="Act fast! These promotions are time-limited.")
                
                await channel.send(embed=embed)
                
                # Commit to database so it doesn't print it out again next check cycle
                await db.posted_freebies.insert_one({
                    "title_key": clean_title,
                    "posted_at": time.time()
                })

    @check_free_games.before_loop
    async def before_checker_starts(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="set_free_games_channel", 
        description="[ADMIN] Bind the automated free game deal updates to a specific text channel."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_channel_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        
        await db.settings.update_one(
            {"setting_id": "free_games_config"},
            {"$set": {"channel_id": str(channel.id)}},
            upsert=True
        )
        
        await interaction.followup.send(
            f"🎯 Success! Automated deals will now feed directly into {channel.mention}.", 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(FreeGamesCog(bot))
