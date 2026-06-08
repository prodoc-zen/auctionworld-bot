import random

import discord
from discord import app_commands
from sqlalchemy import select

from commands.gacha._gacha_utils import get_character_data
from database.models import GachaCard, GachaShowcase

name = "gacha-battle"
description = "Battle using your selected decks"

ELEMENT_ADVANTAGE = {
    "fire": "wind",
    "wind": "earth",
    "earth": "water",
    "water": "fire",
    "light": "dark",
    "dark": "light",
}


def elemental_multiplier(attacker: str, defender: str) -> float:
    if ELEMENT_ADVANTAGE.get(attacker) == defender:
        return 1.2
    if ELEMENT_ADVANTAGE.get(defender) == attacker:
        return 0.9
    return 1.0


def choose_attack(turn: int, cooldowns: dict, attacks: dict) -> tuple[str, dict]:
    for key in ("power_attack", "secondary_attack", "normal_attack"):
        if cooldowns[key] <= turn:
            cooldowns[key] = turn + attacks[key]["cooldown"]
            return key, attacks[key]
    return "normal_attack", attacks["normal_attack"]


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(opponent="Opponent to battle")
    async def gacha_battle(interaction, opponent: discord.Member):
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You cannot battle yourself.", ephemeral=True)
            return

        async with database.session() as session:
            async def load_deck(discord_id: int):
                result = await session.execute(
                    select(GachaShowcase)
                    .where(GachaShowcase.discord_id == discord_id, GachaShowcase.card_id.is_not(None))
                    .order_by(GachaShowcase.slot.asc())
                    .limit(3)
                )
                showcase_rows = result.scalars().all()

                deck = []
                for row in showcase_rows:
                    card = await session.get(GachaCard, row.card_id)
                    if card is None:
                        continue
                    _, data = get_character_data(card.character_name)
                    if data is None:
                        continue

                    attacks = {
                        "normal_attack": data["normal_attack"],
                        "secondary_attack": data["secondary_attack"],
                        "power_attack": data["power_attack"],
                    }
                    scaled_hp = int(data["health"] + ((card.level - 1) * 8))
                    deck.append({
                        "name": card.character_name,
                        "hp": scaled_hp,
                        "element": data["element"],
                        "attacks": attacks,
                        "cooldowns": {"normal_attack": 0, "secondary_attack": 0, "power_attack": 0},
                    })
                return deck

            my_deck = await load_deck(interaction.user.id)
            opp_deck = await load_deck(opponent.id)

        if not my_deck:
            await interaction.response.send_message("Set your decks first using `/gacha-showcase` (up to 3 slots).", ephemeral=True)
            return
        if not opp_deck:
            await interaction.response.send_message(f"{opponent.mention} has no decks set.", ephemeral=True)
            return

        log_lines = []
        my_idx = 0
        opp_idx = 0
        turn = 1

        while my_idx < len(my_deck) and opp_idx < len(opp_deck) and turn <= 150:
            attacker = my_deck[my_idx]
            defender = opp_deck[opp_idx]
            atk_key, atk_data = choose_attack(turn, attacker["cooldowns"], attacker["attacks"])
            mult = elemental_multiplier(attacker["element"], defender["element"])
            dmg = max(1, int(atk_data["damage"] * mult))
            defender["hp"] -= dmg
            log_lines.append(
                f"T{turn}: {attacker['name']} used {atk_data['name']} ({atk_key}) for {dmg} on {defender['name']} ({max(0, defender['hp'])} HP left)"
            )
            if defender["hp"] <= 0:
                log_lines.append(f"💥 {defender['name']} is defeated!")
                opp_idx += 1
                turn += 1
                continue

            attacker2 = opp_deck[opp_idx]
            defender2 = my_deck[my_idx]
            atk_key2, atk_data2 = choose_attack(turn, attacker2["cooldowns"], attacker2["attacks"])
            mult2 = elemental_multiplier(attacker2["element"], defender2["element"])
            dmg2 = max(1, int(atk_data2["damage"] * mult2))
            defender2["hp"] -= dmg2
            log_lines.append(
                f"T{turn}: {attacker2['name']} used {atk_data2['name']} ({atk_key2}) for {dmg2} on {defender2['name']} ({max(0, defender2['hp'])} HP left)"
            )
            if defender2["hp"] <= 0:
                log_lines.append(f"💥 {defender2['name']} is defeated!")
                my_idx += 1

            turn += 1

        if my_idx >= len(my_deck) and opp_idx >= len(opp_deck):
            result_text = "It's a draw."
        elif opp_idx >= len(opp_deck):
            result_text = f"🏆 {interaction.user.mention} wins!"
        else:
            result_text = f"🏆 {opponent.mention} wins!"

        embed = discord.Embed(
            title="⚔️ Gacha Battle",
            description=f"{interaction.user.mention} vs {opponent.mention}\n\n{result_text}",
            color=discord.Color.red(),
        )
        embed.add_field(name="Battle Log", value="\n".join(log_lines[:20]) or "No turns.", inline=False)
        if len(log_lines) > 20:
            embed.set_footer(text=f"Showing 20/{len(log_lines)} log lines")

        await interaction.response.send_message(embed=embed)
