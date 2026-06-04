"""Central application bootloader context for loading separate modular cogs."""
import logging
import discord
from discord.ext import commands

# Silencing core startup warnings
logging.getLogger("discord").setLevel(logging.ERROR)
logging.getLogger("discord.client").setLevel(logging.ERROR)
logging.getLogger("discord.ext.commands.bot").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

_bot: commands.Bot | None = None
_ready = False

def is_running() -> bool:
    return _ready and _bot is not None and not _bot.is_closed()

def _build_bot(db) -> commands.Bot:
    intents = discord.Intents.default()
    intents.voice_states = False  
    intents.message_content = False
    
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
    bot.db = db
    DEV_GUILD_ID = 1469032638395191298 

    @bot.event
    async def setup_hook():
        try:
            # 1. Automatically import and register our modular Dictionary cog
            await bot.load_extension("cogs.dictionary")
            logger.info("Successfully loaded extension: cogs.dictionary")
            
            # 2. Automatically import and register our modular Affirmations cog
            await bot.load_extension("cogs.affirmations")
            logger.info("Successfully loaded extension: cogs.affirmations")
            
            # 3. Automatically import and register our modular Virtual Pet cog
            await bot.load_extension("cogs.virtual_pet")
            logger.info("Successfully loaded extension: cogs.virtual_pet")
            
            # 4. Sync to your server guild instantly for testing updates
            guild = discord.Object(id=DEV_GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Instant Guild Sync Complete! Loaded {len(synced)} command endpoints.")
        except Exception as e:
            logger.exception(f"Failed to cleanly spin up application extensions: {e}")

    @bot.event
    async def on_ready():
        global _ready
        _ready = True
        
        try:
            # Re-hook Dictionary persistent button listeners
            from cogs.dictionary import CardInteractionView
            bot.add_view(CardInteractionView(bot, ""))
            
            # Re-hook Virtual Pet persistent button listeners
            from cogs.virtual_pet import PetControlPanel
            pet_cog = bot.get_cog("VirtualPetCog")
            if pet_cog:
                bot.add_view(PetControlPanel(pet_cog, {}))
                
            logger.info("Persistent button listeners successfully hooked up.")
        except Exception as e:
            logger.error(f"Could not hook global view callback persistence framework: {e}")
            
        logger.info(f"Discord bot ready as {bot.user}")

    return bot

async def start_bot(token: str, db):
    global _bot
    _bot = _build_bot(db)
    await _bot.start(token)

async def stop_bot():
    global _bot, _ready
    _ready = False
    if _bot and not _bot.is_closed():
        await _bot.close()
