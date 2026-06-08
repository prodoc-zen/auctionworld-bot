import discord
from discord import app_commands
from sqlalchemy import select, update

from database.models import AdminProfile, AttendanceRecord, GachaCard, GachaShowcase, Transaction, User

name        = "change-discord"
description = "Replace an admin's Discord account and migrate all their data"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        admin_id="The admin's profile ID (from /profile)",
        new_discord_id="The new Discord account ID (numbers only)",
    )
    async def change_discord(interaction, admin_id: int, new_discord_id: str):
        try:
            new_id = int(new_discord_id.strip())
        except ValueError:
            await interaction.response.send_message(
                "Invalid Discord ID — must be a number.", ephemeral=True,
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

            old_id = profile.discord_id

            if old_id == new_id:
                await interaction.response.send_message(
                    "New Discord ID is the same as the current one.", ephemeral=True,
                )
                return

            # Check new ID isn't already taken
            existing_new = await session.get(User, new_id)
            if existing_new is None:
                session.add(User(discord_id=new_id, jennies=0))
                await session.flush()

            # Migrate users table (merge jennies)
            old_user = await session.get(User, old_id)
            new_user = await session.get(User, new_id)
            if old_user:
                new_user.jennies += old_user.jennies

            # Migrate all related records to new discord_id
            await session.execute(update(AttendanceRecord).where(AttendanceRecord.discord_id == old_id).values(discord_id=new_id))
            await session.execute(update(Transaction).where(Transaction.discord_id == old_id).values(discord_id=new_id))
            await session.execute(update(GachaCard).where(GachaCard.discord_id == old_id).values(discord_id=new_id))
            await session.execute(update(GachaShowcase).where(GachaShowcase.discord_id == old_id).values(discord_id=new_id))

            # Update profile
            profile.discord_id = new_id

            # Delete old user row
            if old_user:
                await session.delete(old_user)

            await session.commit()

        embed = discord.Embed(title="Discord Account Updated ✅", color=discord.Color.green())
        embed.add_field(name="Admin ID",    value=str(admin_id),            inline=False)
        embed.add_field(name="Old Discord", value=f"<@{old_id}>",           inline=False)
        embed.add_field(name="New Discord", value=f"<@{new_id}>",           inline=False)
        embed.add_field(name="Migrated",    value="Attendance, Gacha, Transactions, Jennies", inline=False)
        embed.add_field(name="Changed By",  value=interaction.user.mention, inline=False)

        await interaction.response.send_message(embed=embed)
