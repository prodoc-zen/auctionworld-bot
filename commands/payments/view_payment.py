import discord
from discord import app_commands

from database.models import Payment

name        = "view-payment"
description = "View a payment submission by its ID"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(payment_id="The payment ID to view")
    async def view_payment(interaction, payment_id: int):
        async with database.session() as session:
            payment = await session.get(Payment, payment_id)

        if payment is None:
            await interaction.response.send_message(
                f"Payment `{payment_id}` not found.", ephemeral=True,
            )
            return

        status = "✅ Verified" if payment.verified else "⏳ Pending"
        embed  = discord.Embed(title="Payment Details", color=discord.Color.blurple())
        embed.add_field(name="Payment ID", value=str(payment.id),              inline=False)
        embed.add_field(name="Discord",    value=f"<@{payment.discord_id}>",   inline=False)
        embed.add_field(name="Reason",     value=payment.reason,               inline=False)
        embed.add_field(name="Status",     value=status,                       inline=False)
        if payment.verified_by:
            embed.add_field(name="Verified By", value=f"<@{payment.verified_by}>", inline=False)
        embed.set_image(url=payment.screenshot_url)

        await interaction.response.send_message(embed=embed)
