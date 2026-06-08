import discord
from discord import app_commands
from database.models import User, utc_now
from sqlalchemy import select
from sqlalchemy import Column, BigInteger, Boolean, DateTime, String
from database.models import Base
from datetime import datetime

name        = "submit-megaphone"
description = "Submit proof of megaphone donation"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(screenshot="Screenshot showing your megaphone donation")
    async def submit_megaphone(interaction, screenshot: discord.Attachment):
        async with database.session() as session:
            from database.models import MegaphoneSubmission
            existing = await session.execute(
                select(MegaphoneSubmission).where(
                    MegaphoneSubmission.discord_id == interaction.user.id,
                    MegaphoneSubmission.verified == False,
                )
            )
            if existing.scalar_one_or_none() is not None:
                await interaction.response.send_message(
                    "You already have a pending megaphone submission.", ephemeral=True,
                )
                return

            sub = MegaphoneSubmission(
                discord_id=interaction.user.id,
                screenshot_url=screenshot.url,
            )
            session.add(sub)
            await session.flush()
            sub_id = sub.id
            await session.commit()

        embed = discord.Embed(title="📢 Megaphone Submitted", color=discord.Color.blurple())
        embed.add_field(name="Submission ID", value=str(sub_id),              inline=False)
        embed.add_field(name="Discord",       value=interaction.user.mention, inline=False)
        embed.add_field(name="Status",        value="⏳ Pending verification", inline=False)
        embed.set_image(url=screenshot.url)

        await interaction.response.send_message(embed=embed)
