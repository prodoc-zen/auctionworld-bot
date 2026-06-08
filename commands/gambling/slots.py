import random
import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name        = "slots"
description = "Play the slot machine (min 10, max 1000 Jennies)"

MIN_BET = 10
MAX_BET = 1000

SYMBOLS = [
    ("💎", 100),  # 100x — jackpot
    ("7️⃣",  20),  # 20x
    ("🍒",  10),  # 10x
    ("🔔",   5),  # 5x
    ("⭐",   3),  # 3x
    ("🍋",   2),  # 2x
    ("🍇",   1),  # 1x — return bet
]

# Weights for medium volatility (jackpot is rare)
WEIGHTS = [1, 3, 6, 10, 15, 20, 25]


def spin():
    symbol = random.choices(SYMBOLS, weights=WEIGHTS, k=1)[0]
    return symbol


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(bet="Amount of Jennies to bet (10–1000)")
    async def slots(interaction, bet: int):
        if bet < MIN_BET or bet > MAX_BET:
            await interaction.response.send_message(
                f"Bet must be between {MIN_BET} and {MAX_BET} Jennies.", ephemeral=True,
            )
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
                    f"You only have **{user.jennies} Jennies**.", ephemeral=True,
                )
                return

            reel1 = spin()
            reel2 = spin()
            reel3 = spin()

            display = f"{reel1[0]} | {reel2[0]} | {reel3[0]}"

            if reel1[0] == reel2[0] == reel3[0]:
                # All three match
                multiplier  = reel1[1]
                winnings    = bet * multiplier
                user.jennies += winnings
                result_text  = f"🎰 **JACKPOT! {multiplier}x** — You win **{winnings} Jennies**!"
            elif reel1[0] == reel2[0] or reel2[0] == reel3[0] or reel1[0] == reel3[0]:
                # Two match — half multiplier
                sym = reel1 if reel1[0] == reel2[0] or reel1[0] == reel3[0] else reel2
                winnings    = max(bet, int(bet * sym[1] * 0.5))
                user.jennies += winnings - bet
                result_text  = f"✅ **Two of a kind!** You win **{winnings} Jennies**!"
            else:
                # No match — lose
                user.jennies -= bet
                result_text   = f"❌ No match. You lose **{bet} Jennies**."

            await session.commit()
            new_balance = user.jennies

        embed = discord.Embed(title="🎰 Slots", color=discord.Color.gold())
        embed.add_field(name="Reels",   value=display,              inline=False)
        embed.add_field(name="Result",  value=result_text,          inline=False)
        embed.add_field(name="Balance", value=f"**{new_balance} Jennies**", inline=False)

        await interaction.response.send_message(embed=embed)
