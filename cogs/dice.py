"""Cog handling dynamic dice rolling mechanics for tabletop gaming and server jokes."""
import logging
import random
import re
import time
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

class DiceCog(commands.Cog):
    """Manages dice rolling commands with gaming modifiers and Easter eggs."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="roll", 
        description="Roll gaming dice using standard notation (e.g., 1d20, 2d6+4, or just a number)."
    )
    async def roll_cmd(self, interaction: discord.Interaction, expression: str):
        await interaction.response.defer(thinking=True)
        
        # Clean up input string
        clean_expr = expression.strip().lower().replace(" ", "")
        
        # Regex to parse standard dice notation: NdD(+/-)M
        # Group 1: Number of dice (optional, defaults to 1)
        # Group 2: Number of sides on the dice
        # Group 3: Modifier sign and value (optional, e.g., +4, -2)
        dice_pattern = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$")
        match = dice_pattern.match(clean_expr)
        
        random.seed(time.time())
        
        if match:
            num_dice = int(match.group(1)) if match.group(1) else 1
            sides = int(match.group(2))
            modifier_str = match.group(3)
            
            # Safety caps to prevent server-melting inputs
            if num_dice > 100:
                await interaction.followup.send("⛔ You can't roll more than 100 dice at once! Calm your hands.")
                return
            if sides > 1000 or sides < 2:
                await interaction.followup.send("⛔ Dice must have between 2 and 1000 sides.")
                return
                
            # Roll individual dice
            rolls = [random.randint(1, sides) for _ in range(num_dice)]
            base_total = sum(rolls)
            
            # Parse modifier if it exists
            modifier = 0
            if modifier_str:
                modifier = int(modifier_str)
                
            final_total = base_total + modifier
            
            # Format individual rolls output
            rolls_display = ", ".join(str(r) for r in rolls)
            if len(rolls_display) > 100:
                rolls_display = rolls_display[:97] + "..."
                
            embed = discord.Embed(
                title="🎲 Dice Roll Result",
                color=discord.Color.from_str("#DCD0FF")
            )
            
            # Formulate description details
            desc = f"**Roll:** `{num_dice}d{sides}{modifier_str or ''}`\n"
            desc += f"**Dice Landed On:** `[{rolls_display}]`"
            if modifier != 0:
                desc += f" (Base: {base_total} {modifier_str})\n"
            else:
                desc += "\n"
                
            desc += f"🏆 **Final Total:** **{final_total}**"
            embed.description = desc
            
            # LEVEL 10 EASTER EGG: Max natural roll on a single D20 check!
            if sides == 20 and num_dice == 1 and rolls[0] == 20:
                embed.add_field(
                    name="🌟 CRITICAL SUCCESS", 
                    value="An immaculate critical hit! You are operating at **LEVEL 10** energy right now!"
                )
                embed.color = discord.Color.from_str("#4A3B63")
                
        else:
            # Fallback: Check if they just typed a raw number (e.g., "/roll 6" defaults to a 1d6)
            if clean_expr.isdigit():
                sides = int(clean_expr)
                if sides < 2 or sides > 1000:
                    await interaction.followup.send("⛔ Please provide a valid dice size or notation.")
                    return
                result = random.randint(1, sides)
                embed = discord.Embed(
                    title="🎲 Quick Roll",
                    description=f"Rolled a standard `1d{sides}`.\n🎯 **Result:** **{result}**",
                    color=discord.Color.from_str("#DCD0FF")
                )
            else:
                await interaction.followup.send(
                    "❌ Invalid notation format! Use formats like `1d20`, `2d6+4`, or simply `6`.", 
                    ephemeral=True
                )
                return

        embed.set_footer(text=f"Rolled by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(DiceCog(bot))
