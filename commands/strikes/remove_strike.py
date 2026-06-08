import discord
from discord import app_commands

from database.models import Strike

name        = "remove-strike"
description = "Remove a strike by its ID"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(strike_id="The ID of the strike to remove")
    async def remove_strike(interaction, strike_id: int):
        async with database.session() as session:
            strike = await session.get(Strike, strike_id)

            if strike is None or not strike.active:
                await interaction.response.send_message(
                    f"Strike `{strike_id}` not found or already removed.",
                    ephemeral=True,
                )
                return

            strike.active     = False
            strike.updated_at = strike.updated_at
            await session.commit()

        embed = discord.Embed(title="Strike Removed", color=discord.Color.green())
        embed.add_field(name="Strike ID",   value=str(strike_id),           inline=False)
        embed.add_field(name="User",        value=f"<@{strike.discord_id}>", inline=False)
        embed.add_field(name="Removed By",  value=interaction.user.mention, inline=False)

        await interaction.response.send_message(embed=embed)
