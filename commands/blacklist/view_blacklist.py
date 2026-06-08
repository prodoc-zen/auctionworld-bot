import discord
from sqlalchemy import select
from database.models import Blacklist

name        = "view-blacklist"
description = "View all active blacklisted users"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def view_blacklist(interaction):
        async with database.session() as session:
            result = await session.execute(
                select(Blacklist)
                .where(Blacklist.active == True)
                .order_by(Blacklist.created_at.desc())
            )
            entries = result.scalars().all()

        if not entries:
            await interaction.response.send_message(
                "No users are currently blacklisted.", ephemeral=True,
            )
            return

        lines = [
            f"**#{e.id}** <@{e.discord_id}> — {e.reason}"
            for e in entries[:20]
        ]

        embed = discord.Embed(
            title=f"🚫 Blacklist ({len(entries)} total)",
            description="\n".join(lines),
            color=discord.Color.red(),
        )
        if len(entries) > 20:
            embed.set_footer(text=f"Showing 20 of {len(entries)}")

        await interaction.response.send_message(embed=embed, ephemeral=True)
