import discord
from discord import app_commands
from sqlalchemy import select

from database.models import AdminProfile, AdminUser, User, utc_now

name        = "change-discord"
description = "Replace an admin's Discord account in their profile"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        admin_id="The admin's profile ID (from /profile)",
        new_discord_id="The new Discord account ID (numbers only, not @ or username)",
    )
    async def change_discord(interaction, admin_id: int, new_discord_id: str):
        try:
            new_id = int(new_discord_id.strip())
        except ValueError:
            await interaction.response.send_message(
                "Invalid Discord ID — must be a number. Do not use @ or username.",
                ephemeral=True,
            )
            return

        async with database.session() as session:
            result = await session.execute(
                select(AdminProfile).where(AdminProfile.id == admin_id)
            )
            profile = result.scalar_one_or_none()

            if profile is None:
                await interaction.response.send_message(
                    f"No admin profile found with ID `{admin_id}`.", ephemeral=True,
                )
                return

            old_discord_id    = profile.discord_id
            profile.discord_id = new_id

            # Ensure new user row exists
            if await session.get(User, new_id) is None:
                session.add(User(discord_id=new_id, jennies=0))
                await session.flush()

            # Ensure new admin_user row exists
            if await session.get(AdminUser, new_id) is None:
                session.add(AdminUser(discord_id=new_id, is_active=True))
                await session.flush()

            await session.commit()

        embed = discord.Embed(title="Discord Account Updated ✅", color=discord.Color.green())
        embed.add_field(name="Admin ID",      value=str(admin_id),             inline=False)
        embed.add_field(name="Old Discord",   value=f"<@{old_discord_id}>",    inline=False)
        embed.add_field(name="New Discord",   value=f"<@{new_id}>",            inline=False)
        embed.add_field(name="Changed By",    value=interaction.user.mention,  inline=False)

        await interaction.response.send_message(embed=embed)
