import discord
from discord import app_commands
from sqlalchemy import select
from database.models import MegaphoneSubmission, utc_now

name        = "verify-megaphone"
description = "Verify a megaphone donation submission"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(submission_id="The submission ID to verify")
    async def verify_megaphone(interaction, submission_id: int):
        async with database.session() as session:
            sub = await session.get(MegaphoneSubmission, submission_id)

            if sub is None:
                await interaction.response.send_message(
                    f"Submission `{submission_id}` not found.", ephemeral=True,
                )
                return

            if sub.verified:
                await interaction.response.send_message(
                    f"Submission `{submission_id}` is already verified.", ephemeral=True,
                )
                return

            sub.verified    = True
            sub.verified_by = interaction.user.id
            sub.updated_at  = utc_now()
            await session.commit()

        embed = discord.Embed(title="📢 Megaphone Verified ✅", color=discord.Color.green())
        embed.add_field(name="Submission ID", value=str(submission_id),         inline=False)
        embed.add_field(name="Discord",       value=f"<@{sub.discord_id}>",     inline=False)
        embed.add_field(name="Verified By",   value=interaction.user.mention,   inline=False)
        embed.set_image(url=sub.screenshot_url)

        await interaction.response.send_message(embed=embed)
