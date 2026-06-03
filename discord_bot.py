"""Discord bot handler for the TBD Dictionary system, featuring hybrid text/slash command structures."""
import logging
import json
import discord
from discord import app_commands
from discord.ext import commands
from bson import json_util

logger = logging.getLogger(__name__)

# Define the explicit developer User ID allowed to execute testing wipe operations
# ⚠️ PASTE YOUR ACTUAL 17-19 DIGIT NUMERICAL DISCORD USER ID HERE!
DEVELOPER_USER_ID = 552956853147926532 

class TBD_Bot(commands.Bot):
    def __init__(self, db_connection):
        # Configure default intents (adjust as needed for your specific feature suite)
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.db = db_connection  # Save database handle to self for accessibility across commands

    async def setup_hook(self):
        """Pre-flight setup hook executing right before internal websocket connection opens."""
        logger.info("Synchronizing application command trees...")
        # Syncs slash commands globally. Note: Global syncing can take up to an hour to propagate.
        await self.tree.sync()
        logger.info("Application command trees successfully synchronized globally.")

    async def on_ready(self):
        logger.info(f"✅ Discord Bot logged in successfully as: {self.user.name} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="with the TBD Dictionary!"))


# Initialize an internal placeholder so lifespan hooks can track state
active_bot: TBD_Bot = None


async def start_bot(token: str, db_connection) -> None:
    """Launches the core Discord gateway connection loop as an un-blocking asynchronous task loop."""
    global active_bot
    try:
        active_bot = TBD_Bot(db_connection=db_connection)
        
        # ==========================================
        # COMMAND 1: SLASH COMMAND - /deleteword
        # ==========================================
        @active_bot.tree.command(
            name="deleteword", 
            description="[TESTING ONLY] Force delete a word entry from the TBD Dictionary database."
        )
        @app_commands.describe(word="The exact dictionary word entry you wish to wipe out.")
        async def deleteword_command(interaction: discord.Interaction, word: str):
            """Targeted developer testing route built to slice documents out of MongoDB collections."""
            
            # Verification structural check to prevent standard server users from abusing purges
            if interaction.user.id != DEVELOPER_USER_ID:
                await interaction.response.send_message(
                    "❌ **Permission Denied:** This destructive action is locked exclusively to developers during testing.",
                    ephemeral=True
                )
                return

            if active_bot.db is None:
                await interaction.response.send_message(
                    "❌ **Database Offline:** The bot lost its active link connection to MongoDB Atlas.",
                    ephemeral=True
                )
                return

            # Clean leading/trailing spaces from input
            target_word = word.strip()
            
            # Defer response immediately to prevent standard 3-second Discord timeouts
            await interaction.response.defer(ephemeral=True)

            try:
                # FIXED: Uses case-insensitive regex line anchors (^ and $)
                # This drops documents regardless of lowercase or uppercase mismatches.
                query = {"word": {"$regex": f"^{target_word}$", "$options": "i"}}
                result = await active_bot.db.cards.delete_one(query)
                
                if result.deleted_count > 0:
                    await interaction.followup.send(
                        f"🗑️ **Testing Purge Successful:**\n"
                        f"The word entry matching `“{target_word}”` was vaporized from the collection.",
                        ephemeral=True
                    )
                    logger.info(f"Developer {interaction.user} forcefully dropped word '{target_word}' via slash route.")
                else:
                    await interaction.followup.send(
                        f"❓ **Wipe Missed:** Could not find an entry matching `“{target_word}”` inside the collection.",
                        ephemeral=True
                    )
            except Exception as mongo_error:
                logger.error(f"MongoDB pipeline broke during inline testing wipe: {mongo_error}")
                await interaction.followup.send(
                    f"❌ **Database Pipeline Exception:** Processing error occurred:\n`{str(mongo_error)}`",
                    ephemeral=True
                )

        # ==========================================
        # COMMAND 2: SLASH COMMAND - /debuglist
        # ==========================================
        @active_bot.tree.command(
            name="debuglist", 
            description="[TESTING ONLY] Inspect the raw document structure directly from MongoDB."
        )
        async def debuglist_command(interaction: discord.Interaction):
            """Dumps raw documents from the collection to verify exact schema field names."""
            if interaction.user.id != DEVELOPER_USER_ID:
                await interaction.response.send_message("❌ **Permission Denied.**", ephemeral=True)
                return

            if active_bot.db is None:
                await interaction.response.send_message("❌ **Database Offline.**", ephemeral=True)
                return

            # Defer instantly to prevent Discord's strict 3-second timeout crash
            await interaction.response.defer(ephemeral=True)

            try:
                # Pull the 3 most recent documents to inspect their keys
                cursor = active_bot.db.cards.find().sort("_id", -1).limit(3)
                documents = await cursor.to_list(length=3)

                if not documents:
                    await interaction.followup.send(
                        "⚠️ **Database is completely empty.** No records exist in this collection to inspect.",
                        ephemeral=True
                    )
                    return
                
                raw_dump = json.dumps(documents, default=json_util.default, indent=2)
                
                # Truncate if it exceeds Discord's max message limit length (2000 characters)
                if len(raw_dump) > 1900:
                    raw_dump = raw_dump[:1900] + "\n...[Truncated due to length]"

                await interaction.followup.send(
                    f"🔍 **Raw MongoDB Inspection (Last 3 Entries):**\n```json\n{raw_dump}\n```",
                    ephemeral=True
                )

            except Exception as e:
                logger.error(f"Debug list failed: {e}")
                await interaction.followup.send(f"❌ Diagnostic error: `{str(e)}`", ephemeral=True)

        # Connect directly to the discord gateways using the live token context
        await active_bot.start(token)
        
    except discord.errors.LoginFailure:
        logger.error("❌ Failed to authenticate with Discord. Your DISCORD_TOKEN configuration is invalid.")
        raise
    except Exception as e:
        logger.error(f"Discord core architecture crashed on initialization startup: {e}", exc_info=True)
        raise e


async def stop_bot() -> None:
    """Safely shuts down the active bot connection instance during backend application lifespans."""
    global active_bot
    if active_bot is not None:
        logger.info("Closing active Discord web gateway structures gracefully...")
        await active_bot.close()
        logger.info("Discord engine successfully unmounted and finalized cleanly.")
