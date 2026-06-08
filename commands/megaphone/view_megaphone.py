import discord
from sqlalchemy import select
from database.models import MegaphoneSubmission

name        = "view-megaphone"
description = "View pending megaphone submissions"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def view_megaphone(interaction):
        async with database.session() as session:
            result = await session.execute(
                select(MegaphoneSubmission)
                .where(MegaphoneSubmission.verified == False)
                .order_by(MegaphoneSubmission.created_at.asc())
            )
            pending = result.scalars().all()

        if not pending:
            await interaction.response.send_message(
                "No pending megaphone submissions.", ephemeral=True,
            )
            return

        lines = [
            f"**#{s.id}** <@{s.discord_id}> — {s.created_at.strftime('%d %b %Y')} — [Screenshot]({s.screenshot_url})"
            for s in pending[:20]
        ]

        embed = discord.Embed(
            title=f"📢 Pending Megaphone Submissions ({len(pending)})",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        if len(pending) > 20:
            embed.set_footer(text=f"Showing 20 of {len(pending)}")

        await interaction.response.send_message(embed=embed, ephemeral=True)
