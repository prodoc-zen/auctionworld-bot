import random
import discord
from discord import app_commands
from sqlalchemy import select
from database.models import User

name        = "blackjack"
description = "Play blackjack (min 10, max 1000 Jennies)"

MIN_BET = 10
MAX_BET = 1000

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def card_value(rank):
    if rank in ["J", "Q", "K"]: return 10
    if rank == "A": return 11
    return int(rank)


def hand_value(hand):
    value = sum(card_value(r) for r, _ in hand)
    aces  = sum(1 for r, _ in hand if r == "A")
    while value > 21 and aces:
        value -= 10
        aces  -= 1
    return value


def hand_str(hand, hide_second=False):
    if hide_second:
        return f"{hand[0][0]}{hand[0][1]} ??"
    return " ".join(f"{r}{s}" for r, s in hand)


def build_deck():
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck


def is_soft_17(hand):
    return any(r == "A" for r, _ in hand) and hand_value(hand) == 17


def build_embed(player, dealer, bet, balance, hide_dealer=True, result_text=None):
    embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.dark_green())
    embed.add_field(name="Your Hand",     value=f"{hand_str(player)} — **{hand_value(player)}**", inline=False)
    embed.add_field(name="Dealer's Hand", value=hand_str(dealer, hide_second=hide_dealer) + (f" — **{hand_value(dealer)}**" if not hide_dealer else ""), inline=False)
    if result_text:
        embed.add_field(name="Result",  value=result_text,              inline=False)
    embed.add_field(name="Bet",         value=f"**{bet} Jennies**",     inline=True)
    embed.add_field(name="Balance",     value=f"**{balance} Jennies**", inline=True)
    return embed


class BlackjackView(discord.ui.View):
    def __init__(self, player, dealer, deck, bet, discord_id, database, can_double):
        super().__init__(timeout=60)
        self.player     = player
        self.dealer     = dealer
        self.deck       = deck
        self.bet        = bet
        self.discord_id = discord_id
        self.database   = database

        if not can_double:
            self.remove_item(self.double_down)

    async def get_balance(self):
        async with self.database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == self.discord_id))
            user   = result.scalar_one_or_none()
            return user.jennies if user else 0

    async def end_game(self, interaction, result_text, winnings):
        async with self.database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == self.discord_id))
            user   = result.scalar_one_or_none()
            user.jennies += winnings
            await session.commit()
            balance = user.jennies

        for item in self.children:
            item.disabled = True

        embed = build_embed(self.player, self.dealer, self.bet, balance, hide_dealer=False, result_text=result_text)
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction, button):
        if interaction.user.id != self.discord_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return

        # Remove double down after first hit
        self.remove_item(self.double_down) if hasattr(self, 'double_down') else None

        self.player.append(self.deck.pop())
        val = hand_value(self.player)

        if val > 21:
            await self.end_game(interaction, f"💥 **Bust!** You lose **{self.bet} Jennies**.", -self.bet)
        elif val == 21:
            await self.stand_logic(interaction)
        else:
            balance = await self.get_balance()
            embed   = build_embed(self.player, self.dealer, self.bet, balance)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction, button):
        if interaction.user.id != self.discord_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        await self.stand_logic(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.danger)
    async def double_down(self, interaction, button):
        if interaction.user.id != self.discord_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return

        # Deduct extra bet
        async with self.database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == self.discord_id))
            user   = result.scalar_one_or_none()

            if user.jennies < self.bet:
                await interaction.response.send_message(
                    f"You don't have enough Jennies to double down.", ephemeral=True,
                )
                return

            user.jennies -= self.bet
            await session.commit()

        self.bet *= 2
        self.player.append(self.deck.pop())
        val = hand_value(self.player)

        if val > 21:
            await self.end_game(interaction, f"💥 **Bust after double down!** You lose **{self.bet} Jennies**.", -self.bet)
        else:
            await self.stand_logic(interaction)

    async def stand_logic(self, interaction):
        while hand_value(self.dealer) < 17 or is_soft_17(self.dealer):
            self.dealer.append(self.deck.pop())

        player_val = hand_value(self.player)
        dealer_val = hand_value(self.dealer)

        if dealer_val > 21 or player_val > dealer_val:
            await self.end_game(interaction, f"✅ **You win {self.bet} Jennies!**", self.bet)
        elif player_val == dealer_val:
            await self.end_game(interaction, "🤝 **Push!** Your bet is returned.", 0)
        else:
            await self.end_game(interaction, f"❌ **Dealer wins.** You lose **{self.bet} Jennies**.", -self.bet)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


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

            can_double  = user.jennies >= bet * 2
            user.jennies -= bet
            await session.commit()
            balance = user.jennies

        deck   = build_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        if hand_value(player) == 21:
            winnings = int(bet * 1.5)
            async with database.session() as session:
                result = await session.execute(select(User).where(User.discord_id == interaction.user.id))
                user   = result.scalar_one_or_none()
                user.jennies += bet + winnings
                await session.commit()
                balance = user.jennies

            embed = build_embed(player, dealer, bet, balance, hide_dealer=False,
                                result_text=f"🎉 **Blackjack!** You win **{winnings} Jennies**!")
            await interaction.response.send_message(embed=embed)
            return

        view  = BlackjackView(player, dealer, deck, bet, interaction.user.id, database, can_double)
        embed = build_embed(player, dealer, bet, balance)
        await interaction.response.send_message(embed=embed, view=view)
