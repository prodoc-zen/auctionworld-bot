import random
import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name = "reme"
description = "Play REME Roulette (min 10, max 100000 Jennies)"

MIN_BET = 10
MAX_BET = 100000

SPECIAL_NUMBERS = [0, 19, 28]


def reme_value(num):
    if num in SPECIAL_NUMBERS:
        return 0

    total = sum(int(d) for d in str(num))

    while total >= 10:
        total = sum(int(d) for d in str(total))

    return total


def build_embed(player_num, dealer_num, bet, balance, result):
    embed = discord.Embed(
        title="🎲 REME Roulette",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Dealer's Number",
        value=f"**{dealer_num}**",
        inline=True
    )

    embed.add_field(
        name="Your Number",
        value=f"**{player_num}**",
        inline=True
    )

    if player_num not in SPECIAL_NUMBERS and dealer_num not in SPECIAL_NUMBERS:
        embed.add_field(
            name="Values",
            value=(
                f"Dealer Value: **{reme_value(dealer_num)}**\n"
                f"Your Value: **{reme_value(player_num)}**"
            ),
            inline=False
        )

    embed.add_field(
        name="Result",
        value=result,
        inline=False
    )

    embed.add_field(
        name="Bet",
        value=f"**{bet:,} Jennies**",
        inline=True
    )

    embed.add_field(
        name="Balance",
        value=f"**{balance:,} Jennies**",
        inline=True
    )

    return embed


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        bet="Amount of Jennies to bet (10-100000)"
    )
    async def reme(interaction, bet: int):

        if bet < MIN_BET or bet > MAX_BET:
            await interaction.response.send_message(
                f"Bet must be between {MIN_BET:,} and {MAX_BET:,} Jennies.",
                ephemeral=True
            )
            return

        async with database.session() as session:

            result = await session.execute(
                select(User).where(
                    User.discord_id == interaction.user.id
                )
            )

            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    discord_id=interaction.user.id,
                    jennies=2000
                )
                session.add(user)
                await session.flush()

            if user.jennies < bet:
                await interaction.response.send_message(
                    f"You only have **{user.jennies:,} Jennies**.",
                    ephemeral=True
                )
                return

            user.jennies -= bet
            await session.commit()

        dealer_num = random.randint(0, 36)
        player_num = random.randint(0, 36)

        async with database.session() as session:

            result = await session.execute(
                select(User).where(
                    User.discord_id == interaction.user.id
                )
            )

            user = result.scalar_one_or_none()

            # Dealer special = auto win
            if dealer_num in SPECIAL_NUMBERS:

                result_text = (
                    f"🎲 Dealer spins first and rolls **{dealer_num}**!\n\n"
                    f"💀 Special number!\n"
                    f"Dealer wins automatically.\n"
                    f"You lost **{bet:,} Jennies**."
                )

            # Player special = x3 payout
            elif player_num in SPECIAL_NUMBERS:

                user.jennies += bet * 3

                result_text = (
                    f"🎲 Dealer spins first and rolls **{dealer_num}**.\n\n"
                    f"🎲 You spin and roll **{player_num}**!\n\n"
                    f"✨ Special number!\n"
                    f"You won **{bet * 2:,} Jennies** profit (x3 payout)."
                )

            else:

                dealer_value = reme_value(dealer_num)
                player_value = reme_value(player_num)

                if player_value > dealer_value:

                    user.jennies += bet * 2

                    result_text = (
                        f"🎲 Dealer spins first and rolls **{dealer_num}** "
                        f"(Value **{dealer_value}**).\n\n"
                        f"🎲 You spin and roll **{player_num}** "
                        f"(Value **{player_value}**).\n\n"
                        f"🏆 You win!\n"
                        f"You won **{bet:,} Jennies** profit."
                    )

                else:

                    result_text = (
                        f"🎲 Dealer spins first and rolls **{dealer_num}** "
                        f"(Value **{dealer_value}**).\n\n"
                        f"🎲 You spin and roll **{player_num}** "
                        f"(Value **{player_value}**).\n\n"
                        f"❌ Dealer wins.\n"
                        f"Ties also go to the Dealer."
                    )

            await session.commit()
            balance = user.jennies

        embed = build_embed(
            player_num,
            dealer_num,
            bet,
            balance,
            result_text
        )

        await interaction.response.send_message(
            embed=embed
        )
