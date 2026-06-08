import random
import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name        = "roulette"
description = "Play European roulette"

RED_NUMBERS   = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

BET_TYPES = [
    app_commands.Choice(name="Red",     value="red"),
    app_commands.Choice(name="Black",   value="black"),
    app_commands.Choice(name="Odd",     value="odd"),
    app_commands.Choice(name="Even",    value="even"),
    app_commands.Choice(name="1-18",    value="low"),
    app_commands.Choice(name="19-36",   value="high"),
    app_commands.Choice(name="1st 12",  value="first12"),
    app_commands.Choice(name="2nd 12",  value="second12"),
    app_commands.Choice(name="3rd 12",  value="third12"),
]


def check_win(bet_type, number):
    if number == 0:
        return False, 0
    if bet_type == "red":    return number in RED_NUMBERS, 2
    if bet_type == "black":  return number in BLACK_NUMBERS, 2
    if bet_type == "odd":    return number % 2 == 1, 2
    if bet_type == "even":   return number % 2 == 0, 2
    if bet_type == "low":    return 1 <= number <= 18, 2
    if bet_type == "high":   return 19 <= number <= 36, 2
    if bet_type == "first12":  return 1 <= number <= 12, 3
    if bet_type == "second12": return 13 <= number <= 24, 3
    if bet_type == "third12":  return 25 <= number <= 36, 3
    return False, 0


def number_color(number):
    if number == 0: return "🟢"
    return "🔴" if number in RED_NUMBERS else "⚫"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(bet="Amount of Jennies to bet", bet_type="What to bet on")
    @app_commands.choices(bet_type=BET_TYPES)
    async def roulette(interaction, bet: int, bet_type: app_commands.Choice[str]):
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

            number      = random.randint(0, 36)
            won, mult   = check_win(bet_type.value, number)
            color_emoji = number_color(number)

            if won:
                winnings     = bet * mult
                user.jennies += winnings - bet
                result_text  = f"✅ **You win {winnings:,} Jennies!** ({mult}x)"
            else:
                user.jennies -= bet
                result_text   = f"❌ You lose **{bet:,} Jennies**."

            await session.commit()
            new_balance = user.jennies

        embed = discord.Embed(title="🎡 Roulette", color=discord.Color.red())
        embed.add_field(name="Ball Lands On", value=f"{color_emoji} **{number}**",      inline=False)
        embed.add_field(name="Your Bet",      value=bet_type.name,                      inline=False)
        embed.add_field(name="Result",        value=result_text,                        inline=False)
        embed.add_field(name="Balance",       value=f"**{new_balance:,} Jennies**",     inline=False)

        await interaction.response.send_message(embed=embed)
