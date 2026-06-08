import discord
from discord import app_commands
from sqlalchemy import select

from database.models import AdminProfile, utc_now

name        = "give-priority-ticket"
description = "Give a priority ticket to an admin (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        member="The admin to give a priority ticket to",
        amount="Number of tickets to give (default 1)",
    )
    async def give_priority_ticket(
        interaction,
        member: discord.Member,
        amount: int = 1,
    ):
        user_role_ids = {role.id for role in interaction.user.roles}
        if DEVELOPER_ROLE_ID not in user_role_ids:
            await interaction.response.send_message(
                "Only Developers can give priority tickets.", ephemeral=True,
            )
            return

        if amount < 1:
            await interaction.response.send_message("Amount must be at least 1.", ephemeral=True)
            return

        async with database.session() as session:
            result  = await session.execute(
                select(AdminProfile).where(AdminProfile.discord_id == member.id)
            )
            profile = result.scalar_one_or_none()

            if profile is None:
                await interaction.response.send_message(
                    f"{member.mention} does not have an admin profile.", ephemeral=True,
                )
                return

            profile.priority_tickets += amount
            await session.commit()
            new_total = profile.priority_tickets

        embed = discord.Embed(title="Priority Ticket Given 🎫", color=discord.Color.gold())
        embed.add_field(name="Admin",     value=member.mention,           inline=False)
        embed.add_field(name="Given",     value=str(amount),              inline=False)
        embed.add_field(name="New Total", value=str(new_total),           inline=False)
        embed.add_field(name="Given By",  value=interaction.user.mention, inline=False)

        await interaction.response.send_message(embed=embed)
