import discord
from discord import app_commands
from sqlalchemy import select

from database.models import Strike

name        = "view-strike"
description = "View strikes for a user"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(member="The user to view strikes for")
    async def view_strike(interaction, member: discord.Member):
        async with database.session() as session:
            result = await session.execute(
                select(Strike)
                .where(Strike.discord_id == member.id, Strike.active == True)
                .order_by(Strike.created_at.desc())
            )
            strikes = result.scalars().all()

        if not strikes:
            await interaction.response.send_message(
                f"{member.mention} has no active strikes.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Strikes — {member.display_name}",
            color=discord.Color.orange(),
        )
        for strike in strikes:
            embed.add_field(
                name=f"Strike #{strike.id}",
                value=(
                    f"**Reason:** {strike.reason}\n"
                    f"**Issued By:** <@{strike.issued_by}>\n"
                    f"**Date:** {strike.created_at.strftime('%d %b %Y')}\n"
                    f"**Proof:** [Screenshot]({strike.screenshot_url})"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)
