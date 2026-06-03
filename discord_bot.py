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
            description="[TESTING ONLY] Force delete a word entry from the database."
        )
        @app_commands.describe(word="The exact dictionary word entry you wish to wipe out.")
        async def deleteword_command(interaction: discord.Interaction, word: str):
            if interaction.user.id != DEVELOPER_USER_ID:
                await interaction.response.send_message(
                    "❌ **Permission Denied:** This destructive action is locked exclusively to developers during testing.",
                    ephemeral=True
                )
                return

            if active_bot.db is None:
                await interaction.response.send_message("❌ **Database Offline:** The bot lost its active link connection.", ephemeral=True)
                return

            target_word = word.strip()
            await interaction.response.defer(ephemeral=True)

            try:
                # Case-insensitive query targeting the 'cards' collection
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
                        f"❓ **Wipe Missed:** Could not find an entry matching `“{target_word}”` inside the database. Run `/debuglist` to audit keys.",
                        ephemeral=True
                    )
            except Exception as mongo_error:
                logger.error(f"MongoDB pipeline broke during testing wipe: {mongo_error}")
                await interaction.followup.send(f"❌ **Database Error:** `{str(mongo_error)}`", ephemeral=True)

        # ==========================================
        # COMMAND 2: SLASH COMMAND - /list
        # ==========================================
        @active_bot.tree.command(
            name="list", 
            description="List all words currently saved in the TBD Dictionary."
        )
        async def list_command(interaction: discord.Interaction):
            if active_bot.db is None:
                await interaction.response.send_message("❌ Database connection offline.", ephemeral=True)
                return

            # Tells Discord to wait so it never hits the 3-second timeout limit again
            await interaction.response.defer(ephemeral=False)

            try:
                # Sorts alphabetically by the 'word' field
                cursor = active_bot.db.cards.find().sort("word", 1)
                documents = await cursor.to_list(length=100)

                if not documents:
                    await interaction.followup.send("📖 The dictionary is currently empty!")
                    return

                word_list = []
                for doc in documents:
                    w = doc.get("word") or doc.get("title") or "Unknown Schema Element"
                    word_list.append(f"• **{w}**")

                message_content = "📖 **Current TBD Dictionary Entries:**\n" + "\n".join(word_list)
                
                if len(message_content) > 1950:
                    message_content = message_content[:1900] + "\n...and more entries!"

                await interaction.followup.send(message_content)

            except Exception as e:
                logger.error(f"Failed to compile /list output: {e}")
                await interaction.followup.send(f"❌ Failed to fetch list: `{str(e)}`")

        # ==========================================
