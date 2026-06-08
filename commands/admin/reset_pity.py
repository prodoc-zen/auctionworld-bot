import discord
from discord import app_commands
from database.models import GachaPity

name        = "reset-pity"
description = "Reset a user's gacha pity counter (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(member="The user whose pity to reset")
    async def reset_pity(interaction, member: discord.Member):
        if DEVELOPER_ROLE_ID not in {role.id for role in interaction.user.roles}:
            await interaction.response.send_message("Only Developers can use this.", ephemeral=True)
            return

        async with database.session() as session:
            pity = await session.get(GachaPity, member.id)
            if pity is None:
                await interaction.response.send_message(
                    f"{member.mention} has no pity data.", ephemeral=True,
                )
                return

            pity.pulls_since_4star = 0
            pity.pulls_since_3star = 0
            await session.commit()

        await interaction.response.send_message(
            f"✅ Pity reset for {member.mention}.", ephemeral=True,
        )
