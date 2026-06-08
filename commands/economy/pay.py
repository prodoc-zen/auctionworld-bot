import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name        = "pay"
description = "Transfer Jennies to another user"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        member="The user to pay",
        amount="Amount of Jennies to transfer",
    )
    async def pay(interaction, member: discord.Member, amount: int):
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't pay yourself.", ephemeral=True,
            )
            return

        if amount <= 0:
            await interaction.response.send_message(
                "Amount must be positive.", ephemeral=True,
            )
            return

        async with database.session() as session:
            sender_result = await session.execute(select(User).where(User.discord_id == interaction.user.id))
            sender        = sender_result.scalar_one_or_none()

            if sender is None:
                sender = User(discord_id=interaction.user.id, jennies=2000)
                session.add(sender)
                await session.flush()

            if sender.jennies < amount:
                await interaction.response.send_message(
                    f"You only have **{sender.jennies} Jennies**.", ephemeral=True,
                )
                return

            receiver_result = await session.execute(select(User).where(User.discord_id == member.id))
            receiver        = receiver_result.scalar_one_or_none()

            if receiver is None:
                receiver = User(discord_id=member.id, jennies=2000)
                session.add(receiver)
                await session.flush()

            sender.jennies   -= amount
            receiver.jennies += amount
            await session.commit()

        embed = discord.Embed(title="💸 Payment Sent", color=discord.Color.green())
        embed.add_field(name="From",    value=interaction.user.mention, inline=True)
        embed.add_field(name="To",      value=member.mention,           inline=True)
        embed.add_field(name="Amount",  value=f"**{amount} Jennies**",  inline=False)
        embed.add_field(name="Your New Balance", value=f"{sender.jennies} Jennies", inline=False)

        await interaction.response.send_message(embed=embed)
