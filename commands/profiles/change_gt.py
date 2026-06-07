import discord
from discord import app_commands

from database.models import AdminProfile, utc_now

name        = "change-gt"
description = "Change an admin's GT name in their profile"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        admin_id="The admin's profile ID (from /profile)",
        new_gt_name="Their new GrowID",
    )
    async def change_gt(interaction, admin_id: int, new_gt_name: str):
        async with database.session() as session:
            result = await session.execute(
                __import__('sqlalchemy', fromlist=['select']).select(AdminProfile)
                .where(AdminProfile.id == admin_id)
            )
            profile = result.scalar_one_or_none()

            if profile is None:
                await interaction.response.send_message(
                    f"No admin profile found with ID `{admin_id}`.", ephemeral=True,
                )
                return

            old_gt         = profile.gt_name
            profile.gt_name = new_gt_name
            await session.commit()

        embed = discord.Embed(title="GT Name Updated ✅", color=discord.Color.green())
        embed.add_field(name="Admin ID",   value=str(admin_id),           inline=False)
        embed.add_field(name="Discord",    value=f"<@{profile.discord_id}>", inline=False)
        embed.add_field(name="Old GT Name",value=old_gt,                  inline=False)
        embed.add_field(name="New GT Name",value=new_gt_name,             inline=False)
        embed.add_field(name="Changed By", value=interaction.user.mention, inline=False)

        await interaction.response.send_message(embed=embed)
