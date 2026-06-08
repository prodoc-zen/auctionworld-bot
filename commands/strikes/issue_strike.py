import discord
from discord import app_commands
from sqlalchemy import select

from database.models import Strike, User, utc_now

name        = "issue-strike"
description = "Issue a strike to a user"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        member="The user to strike",
        reason="Reason for the strike",
        screenshot="Screenshot proof of misconduct",
    )
    async def issue_strike(
        interaction,
        member:     discord.Member,
        reason:     str,
        screenshot: discord.Attachment,
    ):
        async with database.session() as session:
            if await session.get(User, member.id) is None:
                session.add(User(discord_id=member.id, jennies=0))
                await session.flush()

            strike = Strike(
                discord_id=member.id,
                issued_by=interaction.user.id,
                reason=reason,
                screenshot_url=screenshot.url,
            )
            session.add(strike)
            await session.flush()
            strike_id = strike.id
            await session.commit()

        embed = discord.Embed(title="Strike Issued", color=discord.Color.red())
        embed.add_field(name="Strike ID",  value=str(strike_id),           inline=False)
        embed.add_field(name="User",       value=member.mention,           inline=False)
        embed.add_field(name="Reason",     value=reason,                   inline=False)
        embed.add_field(name="Issued By",  value=interaction.user.mention, inline=False)
        embed.set_image(url=screenshot.url)

        await interaction.response.send_message(embed=embed)
