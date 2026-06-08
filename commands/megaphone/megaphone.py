import discord
from discord import app_commands
from sqlalchemy import select
from database.models import MegaphoneSubmission

name        = "megaphone"
description = "Check if you are exempt from the megaphone donation"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def megaphone(interaction):
        async with database.session() as session:
            result = await session.execute(
                select(MegaphoneSubmission).where(
                    MegaphoneSubmission.discord_id == interaction.user.id,
                    MegaphoneSubmission.verified == True,
                )
            )
            verified = result.scalar_one_or_none()

            pending_result = await session.execute(
                select(MegaphoneSubmission).where(
                    MegaphoneSubmission.discord_id == interaction.user.id,
                    MegaphoneSubmission.verified == False,
                )
            )
            pending = pending_result.scalar_one_or_none()

        if verified:
            await interaction.response.send_message(
                f"✅ {interaction.user.mention}, you are **exempt** from the megaphone donation.",
                ephemeral=True,
            )
        elif pending:
            await interaction.response.send_message(
                f"⏳ {interaction.user.mention}, your submission is **pending verification**.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ {interaction.user.mention}, you are **not exempt**. Use `/submit-megaphone` to submit proof.",
                ephemeral=True,
            )
