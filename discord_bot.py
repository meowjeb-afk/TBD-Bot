"""Discord bot for TBD Dictionary. Runs as background task inside FastAPI."""
import os
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from image_generator import generate_card_image, GENERATED_DIR

logger = logging.getLogger(__name__)

_bot: commands.Bot | None = None
_db = None  # motor db handle, set on start
_ready = False


def is_running() -> bool:
    return _ready and _bot is not None and not _bot.is_closed()


def bot_user_name() -> str | None:
    if _bot and _bot.user:
        return f"{_bot.user.name}"
    return None


def guild_count() -> int:
    if _bot:
        return len(_bot.guilds)
    return 0


def invite_url() -> str | None:
    if _bot and _bot.user:
        return (
            f"https://discord.com/api/oauth2/authorize?client_id={_bot.user.id}"
            "&permissions=2147485696&scope=bot%20applications.commands"
        )
    return None


def _build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = False
    bot = commands.Bot(command_prefix="!", intents=intents)

    # === UPDATE THIS REPLACEMENT WITH YOUR ACTUAL DISCORD SERVER ID ===
    DEV_GUILD_ID = 1469032638395191298  # <-- Replace with your server ID!
    # ==================================================================

    @bot.event
    async def setup_hook():
        try:
            guild = discord.Object(id=DEV_GUILD_ID)
            # Copy our global slash commands directly into your test guild context
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Instant Guild Sync Complete! Synced {len(synced)} commands straight to server {DEV_GUILD_ID}.")
        except Exception as e:
            logger.exception(f"Failed to sync slash commands in setup_hook: {e}")

    @bot.event
    async def on_ready():
        global _ready
        _ready = True
        logger.info(f"Discord bot ready as {bot.user} running across {len(bot.guilds)} guild(s)")

    @bot.tree.command(name="add", description="Add a word to the TBD dictionary")
    @app_commands.describe(word="The word to add", definition="What does it mean?")
    async def add_cmd(interaction: discord.Interaction, word: str, definition: str):
        await interaction.response.defer(thinking=True)
        word_clean = word.strip()
        word_lower = word_clean.lower()

        existing = await _db.words.find_one({"word_lower": word_lower})
        if existing:
            await interaction.followup.send(f"`{word_clean}` is already in the dictionary, meow.")
            return

        posted_by = interaction.user.display_name
        count = await _db.words.count_documents({})
        pose_index = count % 6

        try:
            image_file = await generate_card_image(
                word=word_clean, definition=definition.strip(),
                posted_by=posted_by, pose_index=pose_index,
            )
        except Exception as e:
            logger.exception("image gen failed")
            await interaction.followup.send(f"Couldn't generate the card image. ({e})")
            return

        doc = {
            "id": str(uuid.uuid4()),
            "word": word_clean,
            "word_lower": word_lower,
            "definition": definition.strip(),
            "posted_by": posted_by,
            "discord_user_id": str(interaction.user.id),
            "discord_guild_id": str(interaction.guild_id) if interaction.guild_id else None,
            "image_file": image_file,
            "upvotes": 0,
            "upvoters": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pose_index": pose_index,
        }
        await _db.words.insert_one(doc)

        path = GENERATED_DIR / image_file
        with open(path, "rb") as f:
            data = f.read()
        file = discord.File(io.BytesIO(data), filename=f"{word_lower}.png")
        await interaction.followup.send(
            content=f"**{word_clean}** added to the dictionary, posted by {interaction.user.mention}!",
            file=file,
        )

    @bot.tree.command(name="lookup", description="Look up a word in the TBD dictionary")
    @app_commands.describe(word="The word to look up")
    async def lookup_cmd(interaction: discord.Interaction, word: str):
        await interaction.response.defer(thinking=True)
        doc = await _db.words.find_one({"word_lower": word.strip().lower()})
        if not doc:
            await interaction.followup.send(f"`{word}` is not in the dictionary yet. Add it with `/add`.")
            return
        path = GENERATED_DIR / doc["image_file"] if doc.get("image_file") else None
        if path and path.exists():
            with open(path, "rb") as f:
                data = f.read()
            file = discord.File(io.BytesIO(data), filename=f"{doc['word_lower']}.png")
            await interaction.followup.send(
                content=(
                    f"**{doc['word']}** — posted by {doc['posted_by']} "
                    f"· {doc['upvotes']} uppies"
                ),
                file=file,
            )
        else:
            await interaction.followup.send(
                f"**{doc['word']}** — {doc['definition']} (posted by {doc['posted_by']})"
            )

    @bot.tree.command(name="list", description="List all words in the TBD dictionary")
    async def list_cmd(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        cursor = _db.words.find({}, {"_id": 0}).sort([("word_lower", 1)]).limit(200)
        docs = await cursor.to_list(length=200)
        if not docs:
            await interaction.followup.send("The dictionary is empty. Be the first to add a word with `/add`!")
            return
        lines = [f"**TBD Dictionary** — {len(docs)} word(s):"]
        for d in docs:
            lines.append(f"• **{d['word']}** — {d['definition'][:80]} _(by {d['posted_by']}, {d['upvotes']} uppies)_")
        content = "\n".join(lines)
        if len(content) > 1900:
            content = content[:1900] + "\n... (truncated, see dashboard for full list)"
        await interaction.followup.send(content)

    @bot.tree.command(name="delete", description="Delete a word from the TBD dictionary")
    @app_commands.describe(word="The word to delete")
    async def delete_cmd(interaction: discord.Interaction, word: str):
        await interaction.response.defer(thinking=True)
        doc = await _db.words.find_one({"word_lower": word.strip().lower()})
        if not doc:
            await interaction.followup.send(f"`{word}` is not in the dictionary.")
            return
        is_owner = str(interaction.user.id) == doc.get("discord_user_id")
        is_admin = bool(interaction.user.guild_permissions.manage_messages) if interaction.guild else False
        if not (is_owner or is_admin):
            await interaction.followup.send(
                "Only the original poster or a server moderator can delete this word."
            )
            return
        if doc.get("image_file"):
            try:
                (GENERATED_DIR / doc["image_file"]).unlink(missing_ok=True)
            except Exception:
                pass
        await _db.words.delete_one({"_id": doc["_id"]})
        await interaction.followup.send(f"Deleted **{doc['word']}** from the dictionary.")

    return bot


async def start_bot(token: str, db):
    """Start the Discord bot. Called from FastAPI startup."""
    global _bot, _db
    _db = db
    _bot = _build_bot()
    try:
        await _bot.start(token)
    except Exception as e:
        logger.exception(f"Discord bot crashed: {e}")


async def stop_bot():
    global _bot, _ready
    _ready = False
    if _bot and not _bot.is_closed():
        try:
            await _bot.close()
        except Exception:
            pass
