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
    ("💎", 100),
    ("7️⃣",  20),
    ("🍒",  10),
    ("🔔",   5),
    ("⭐",   3),
    ("🍋",   2),
    ("🍇",   1),
]
WEIGHTS = [1, 3, 6, 10, 15, 20, 25]


def spin():
    return random.choices(SYMBOLS, weights=WEIGHTS, k=1)[0]


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

            # Deduct bet upfront
            user.jennies -= bet

            if reel1[0] == reel2[0] == reel3[0]:
                # All three match — full multiplier
                winnings    = bet * reel1[1]
                user.jennies += winnings
                result_text  = f"🎰 **JACKPOT! {reel1[1]}x** — You win **{winnings} Jennies**!"
            elif reel1[0] == reel2[0] or reel2[0] == reel3[0] or reel1[0] == reel3[0]:
                # Two match — return bet + half multiplier bonus
                sym          = reel1 if (reel1[0] == reel2[0] or reel1[0] == reel3[0]) else reel2
                bonus        = max(1, int(bet * sym[1] * 0.25))
                winnings     = bet + bonus
                user.jennies += winnings
                result_text  = f"✅ **Two of a kind!** You win **{winnings} Jennies** (+{bonus} bonus)!"
            else:
                # No match — bet already deducted
                result_text = f"❌ No match. You lose **{bet} Jennies**."

            await session.commit()
            new_balance = user.jennies

        embed = discord.Embed(title="🎰 Slots", color=discord.Color.gold())
        embed.add_field(name="Reels",   value=display,                     inline=False)
        embed.add_field(name="Result",  value=result_text,                 inline=False)
        embed.add_field(name="Balance", value=f"**{new_balance} Jennies**", inline=False)

        await interaction.response.send_message(embed=embed)
