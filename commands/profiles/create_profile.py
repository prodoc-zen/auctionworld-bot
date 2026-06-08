import discord
from discord import app_commands
from sqlalchemy import select

from database.models import AdminProfile, User

name        = "create-profile"
description = "Manually create an admin profile"

ROLE_CHOICES = [
    app_commands.Choice(name="Basic Admin",   value="Basic Admin"),
    app_commands.Choice(name="Admin Upgrade", value="Admin Upgrade"),
]


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        member="The admin to create a profile for",
        gt_name="Their GrowID (must match exactly)",
        role="Their admin role",
    )
    @app_commands.choices(role=ROLE_CHOICES)
    async def create_profile(
        interaction,
        member:  discord.Member,
        gt_name: str,
        role:    app_commands.Choice[str],
    ):
        discord_id = member.id

        async with database.session() as session:
            # Correct check — query by discord_id not primary key
            existing_result = await session.execute(
                select(AdminProfile).where(AdminProfile.discord_id == discord_id)
            )
            existing = existing_result.scalar_one_or_none()

            if existing is not None:
                await interaction.response.send_message(
                    f"{member.mention} already has a profile (Admin ID: `{existing.id}`).",
                    ephemeral=True,
                )
                return

            if await session.get(User, discord_id) is None:
                session.add(User(discord_id=discord_id, jennies=2000))
                await session.flush()

            profile = AdminProfile(
                discord_id=discord_id,
                gt_name=gt_name,
                role=role.value,
            )
            session.add(profile)
            await session.flush()
            profile_id = profile.id
            await session.commit()

        embed = discord.Embed(title="Admin Profile Created ✅", color=discord.Color.green())
        embed.add_field(name="Admin ID", value=str(profile_id), inline=False)
        embed.add_field(name="Discord",  value=member.mention,  inline=False)
        embed.add_field(name="GT Name",  value=gt_name,         inline=False)
        embed.add_field(name="Role",     value=role.value,       inline=False)

        await interaction.response.send_message(embed=embed)
