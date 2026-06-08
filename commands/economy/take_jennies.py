import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name        = "take-jennies"
description = "Take Jennies from a user (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        member="The user to take Jennies from",
        amount="Amount of Jennies to take",
        reason="Reason (optional)",
    )
    async def take_jennies(interaction, member: discord.Member, amount: int, reason: str = "Manual adjustment"):
        if DEVELOPER_ROLE_ID not in {role.id for role in interaction.user.roles}:
            await interaction.response.send_message("Only Developers can use this command.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == member.id))
            user   = result.scalar_one_or_none()

            if user is None:
                await interaction.response.send_message(
                    f"{member.mention} has no Jennies balance.", ephemeral=True,
                )
                return

            user.jennies = max(0, user.jennies - amount)
            await session.commit()
            new_balance = user.jennies

        embed = discord.Embed(title="💸 Jennies Taken", color=discord.Color.red())
        embed.add_field(name="User",        value=member.mention,           inline=False)
        embed.add_field(name="Amount",      value=f"-{amount} Jennies",     inline=False)
        embed.add_field(name="New Balance", value=f"{new_balance} Jennies", inline=False)
        embed.add_field(name="Reason",      value=reason,                   inline=False)
        embed.add_field(name="By",          value=interaction.user.mention, inline=False)

        await interaction.response.send_message(embed=embed)
