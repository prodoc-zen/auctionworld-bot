import discord
from discord import app_commands

from database.models import Blacklist, User, utc_now

name        = "add-blacklist"
description = "Add a user to the blacklist"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        member="The user to blacklist",
        reason="Reason for blacklisting",
        screenshot="Screenshot proof",
    )
    async def add_blacklist(
        interaction,
        member:     discord.Member,
        reason:     str,
        screenshot: discord.Attachment,
    ):
        async with database.session() as session:
            # Check if already blacklisted
            from sqlalchemy import select
            result = await session.execute(
                select(Blacklist).where(
                    Blacklist.discord_id == member.id,
                    Blacklist.active == True,
                )
            )
            if result.scalar_one_or_none() is not None:
                await interaction.response.send_message(
                    f"{member.mention} is already blacklisted.",
                    ephemeral=True,
                )
                return

            if await session.get(User, member.id) is None:
                session.add(User(discord_id=member.id, jennies=0))
                await session.flush()

            entry = Blacklist(
                discord_id=member.id,
                reason=reason,
            )
            session.add(entry)
            await session.flush()
            entry_id = entry.id
            await session.commit()

        embed = discord.Embed(title="User Blacklisted 🚫", color=discord.Color.red())
        embed.add_field(name="Blacklist ID", value=str(entry_id),           inline=False)
        embed.add_field(name="User",         value=member.mention,          inline=False)
        embed.add_field(name="Reason",       value=reason,                  inline=False)
        embed.add_field(name="Added By",     value=interaction.user.mention, inline=False)
        embed.set_image(url=screenshot.url)

        await interaction.response.send_message(embed=embed)
