import random
import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name = "reme"
description = "Play REME Roulette"

SPECIAL_NUMBERS = [0, 19, 28]


def reme_value(num):
    if num in SPECIAL_NUMBERS:
        return 0
    total = sum(int(d) for d in str(num))
    while total >= 10:
        total = sum(int(d) for d in str(total))
    return total


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(bet="Amount of Jennies to bet")
    async def reme(interaction, bet: int):
        if bet < 1:
            await interaction.response.send_message("Bet must be at least 1 Jennie.", ephemeral=True)
            return

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == interaction.user.id))
            user   = result.scalar_one_or_none()
            if user is None:
                user = User(discord_id=interaction.user.id, jennies=2000)
                session.add(user)
                await session.flush()

            if user.jennies < bet:
                await interaction.response.send_message(
                    f"You only have **{user.jennies:,} Jennies**.", ephemeral=True,
                )
                return

            user.jennies -= bet
            await session.commit()

        dealer_num = random.randint(0, 36)
        player_num = random.randint(0, 36)

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == interaction.user.id))
            user   = result.scalar_one_or_none()

            if dealer_num in SPECIAL_NUMBERS:
                result_text = (
                    f"🎲 Dealer rolls **{dealer_num}** — Special number!\n"
                    f"❌ Dealer wins automatically. You lose **{bet:,} Jennies**."
                )
            elif player_num in SPECIAL_NUMBERS:
                user.jennies += bet * 3
                result_text = (
                    f"🎲 Dealer rolls **{dealer_num}**.\n"
                    f"🎲 You roll **{player_num}** — Special number!\n"
                    f"✅ **x3 payout!** You win **{bet * 2:,} Jennies** profit."
                )
            else:
                dealer_value = reme_value(dealer_num)
                player_value = reme_value(player_num)
                if player_value > dealer_value:
                    user.jennies += bet * 2
                    result_text = (
                        f"🎲 Dealer rolls **{dealer_num}** (Value **{dealer_value}**).\n"
                        f"🎲 You roll **{player_num}** (Value **{player_value}**).\n"
                        f"✅ **You win {bet:,} Jennies** profit!"
                    )
                else:
                    result_text = (
                        f"🎲 Dealer rolls **{dealer_num}** (Value **{dealer_value}**).\n"
                        f"🎲 You roll **{player_num}** (Value **{player_value}**).\n"
                        f"❌ Dealer wins. Ties go to the Dealer."
                    )

            await session.commit()
            balance = user.jennies

        embed = discord.Embed(title="🎲 REME Roulette", color=discord.Color.gold())
        embed.add_field(name="Result",  value=result_text,                 inline=False)
        embed.add_field(name="Bet",     value=f"**{bet:,} Jennies**",      inline=True)
        embed.add_field(name="Balance", value=f"**{balance:,} Jennies**",  inline=True)

        await interaction.response.send_message(embed=embed)
