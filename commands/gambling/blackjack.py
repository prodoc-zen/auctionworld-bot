import random
import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name        = "blackjack"
description = "Play blackjack (min 10, max 1000 Jennies)"

MIN_BET = 10
MAX_BET = 1000

SUITS  = ["♠", "♥", "♦", "♣"]
RANKS  = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def card_value(rank):
    if rank in ["J", "Q", "K"]:
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_value(hand):
    value = sum(card_value(r) for r, _ in hand)
    aces  = sum(1 for r, _ in hand if r == "A")
    while value > 21 and aces:
        value -= 10
        aces  -= 1
    return value


def hand_str(hand):
    return " ".join(f"{r}{s}" for r, s in hand)


def draw(deck):
    return deck.pop()


def build_deck():
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck


def is_soft_17(hand):
    has_ace = any(r == "A" for r, _ in hand)
    return has_ace and hand_value(hand) == 17


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(bet="Amount of Jennies to bet (10–1000)")
    async def blackjack(interaction, bet: int):
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

            deck   = build_deck()
            player = [draw(deck), draw(deck)]
            dealer = [draw(deck), draw(deck)]

            player_val = hand_value(player)
            dealer_val = hand_value(dealer)

            # Dealer hits until 17+ (stands on soft 17)
            while hand_value(dealer) < 17 or is_soft_17(dealer):
                dealer.append(draw(deck))

            dealer_val = hand_value(dealer)

            # Determine result
            if player_val == 21 and len(player) == 2:
                winnings = int(bet * 1.5)
                result_text = f"🎉 **Blackjack!** You win **{winnings} Jennies**!"
                user.jennies += winnings
            elif player_val > 21:
                winnings = -bet
                result_text = f"💥 **Bust!** You lose **{bet} Jennies**."
                user.jennies -= bet
            elif dealer_val > 21 or player_val > dealer_val:
                winnings = bet
                result_text = f"✅ **You win {bet} Jennies!**"
                user.jennies += bet
            elif player_val == dealer_val:
                winnings = 0
                result_text = "🤝 **Push!** Your bet is returned."
            else:
                winnings = -bet
                result_text = f"❌ **Dealer wins.** You lose **{bet} Jennies**."
                user.jennies -= bet

            await session.commit()
            new_balance = user.jennies

        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_green())
        embed.add_field(name="Your Hand",    value=f"{hand_str(player)} — **{player_val}**", inline=False)
        embed.add_field(name="Dealer's Hand",value=f"{hand_str(dealer)} — **{dealer_val}**", inline=False)
        embed.add_field(name="Result",       value=result_text,                              inline=False)
        embed.add_field(name="Balance",      value=f"**{new_balance} Jennies**",             inline=False)

        await interaction.response.send_message(embed=embed)
