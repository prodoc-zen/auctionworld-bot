import discord
from discord import app_commands

from database.models import AdminProfile, AdminUser, Payment, User, utc_now

name        = "submit-payment"
description = "Submit payment proof to create or upgrade an admin profile"

ROLES = ["Basic Admin", "Admin Upgrade"]


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        reason="Basic Admin (side admin) or Admin Upgrade (mid admin)",
        gt_name="Your GrowID (must match exactly)",
        screenshot="Screenshot showing your purchase",
    )
    @app_commands.choices(reason=[
        app_commands.Choice(name="Basic Admin",    value="Basic Admin"),
        app_commands.Choice(name="Admin Upgrade",  value="Admin Upgrade"),
    ])
    async def submit_payment(
        interaction,
        reason:     app_commands.Choice[str],
        gt_name:    str,
        screenshot: discord.Attachment,
    ):
        discord_id = interaction.user.id

        async with database.session() as session:
            if await session.get(User, discord_id) is None:
                session.add(User(discord_id=discord_id, jennies=0))
                await session.flush()

            payment = Payment(
                discord_id=discord_id,
                reason=reason.value,
                screenshot_url=screenshot.url,
            )
            session.add(payment)
            await session.flush()
            payment_id = payment.id
            await session.commit()

        embed = discord.Embed(
            title="Payment Submitted",
            description="A moderator will verify your payment shortly.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Payment ID", value=str(payment_id),       inline=False)
        embed.add_field(name="Discord",    value=interaction.user.mention, inline=False)
        embed.add_field(name="GT Name",    value=gt_name,               inline=False)
        embed.add_field(name="Reason",     value=reason.value,          inline=False)
        embed.set_image(url=screenshot.url)

        await interaction.response.send_message(embed=embed)
