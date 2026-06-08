import discord
from discord import app_commands
from sqlalchemy import select

from database.models import Blacklist, utc_now

name        = "remove-blacklist"
description = "Remove a user from the blacklist"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(member="The user to remove from the blacklist")
    async def remove_blacklist(interaction, member: discord.Member):
        async with database.session() as session:
            result = await session.execute(
                select(Blacklist).where(
                    Blacklist.discord_id == member.id,
                    Blacklist.active == True,
                )
            )
            entry = result.scalar_one_or_none()

            if entry is None:
                await interaction.response.send_message(
                    f"{member.mention} is not on the blacklist.",
                    ephemeral=True,
                )
                return

            entry.active      = False
            entry.removed_by  = interaction.user.id
            entry.updated_at  = utc_now()
            await session.commit()

        embed = discord.Embed(title="Blacklist Removed ✅", color=discord.Color.green())
        embed.add_field(name="User",       value=member.mention,           inline=False)
        embed.add_field(name="Removed By", value=interaction.user.mention, inline=False)

        await interaction.response.send_message(embed=embed)
