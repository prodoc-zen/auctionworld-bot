import discord
from discord import app_commands

from database.models import AdminProfile, AdminUser, Payment, User, utc_now

name        = "verify-payment"
description = "Verify a payment and create or upgrade the admin profile"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        payment_id="The payment ID to verify (use /view-payment first)",
        gt_name="The admin's GrowID",
    )
    async def verify_payment(interaction, payment_id: int, gt_name: str):
        async with database.session() as session:
            payment = await session.get(Payment, payment_id)

            if payment is None:
                await interaction.response.send_message(
                    f"Payment `{payment_id}` not found.", ephemeral=True,
                )
                return

            if payment.verified:
                await interaction.response.send_message(
                    f"Payment `{payment_id}` is already verified.", ephemeral=True,
                )
                return

            payment.verified    = True
            payment.verified_by = interaction.user.id
            payment.updated_at  = utc_now()

            discord_id = payment.discord_id

            # Ensure user exists
            if await session.get(User, discord_id) is None:
                session.add(User(discord_id=discord_id, jennies=0))
                await session.flush()

            # Ensure admin_user exists
            if await session.get(AdminUser, discord_id) is None:
                session.add(AdminUser(discord_id=discord_id, is_active=True))
                await session.flush()

            # Create or update admin profile
            profile = await session.get(AdminProfile, discord_id)
            if profile is None:
                session.add(AdminProfile(
                    discord_id=discord_id,
                    gt_name=gt_name,
                    role=payment.reason,
                ))
            else:
                profile.role    = payment.reason
                profile.gt_name = gt_name

            await session.commit()

        embed = discord.Embed(title="Payment Verified ✅", color=discord.Color.green())
        embed.add_field(name="Payment ID",   value=str(payment_id),              inline=False)
        embed.add_field(name="Discord",      value=f"<@{payment.discord_id}>",   inline=False)
        embed.add_field(name="GT Name",      value=gt_name,                      inline=False)
        embed.add_field(name="Role",         value=payment.reason,               inline=False)
        embed.add_field(name="Verified By",  value=interaction.user.mention,     inline=False)

        await interaction.response.send_message(embed=embed)
