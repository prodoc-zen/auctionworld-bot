import discord
from discord import app_commands
from sqlalchemy import select

from commands.gacha._gacha_utils import STAR_EMOJIS, get_character_image_for_session
from database.models import GachaCard, GachaShowcase

name = "gacha-decks"
description = "View your 3 selected gacha decks with images"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(member="Whose decks to view (leave blank for yourself)")
    async def gacha_decks(interaction, member: discord.Member = None):
        target = member or interaction.user
        discord_id = target.id

        async with database.session() as session:
            result = await session.execute(
                select(GachaShowcase)
                .where(GachaShowcase.discord_id == discord_id)
                .order_by(GachaShowcase.slot.asc())
            )
            slots = result.scalars().all()

            card_map = {}
            for slot in slots:
                if slot.card_id is None:
                    continue
                card = await session.get(GachaCard, slot.card_id)
                if card is not None:
                    card_map[slot.slot] = card

            if not card_map:
                await interaction.response.send_message(
                    f"{target.mention} has no decks set. Use `/gacha-showcase` to set up to 3 decks.",
                    ephemeral=True,
                )
                return

            embeds = []
            for slot in [1, 2, 3]:
                card = card_map.get(slot)
                if card is None:
                    embed = discord.Embed(
                        title=f"Deck Slot {slot}",
                        description="Empty",
                        color=discord.Color.dark_grey(),
                    )
                    embeds.append(embed)
                    continue

                image = await get_character_image_for_session(session, card.character_name)
                embed = discord.Embed(
                    title=f"Deck Slot {slot}",
                    description=f"{STAR_EMOJIS[card.rarity]} **{card.character_name}**\nLevel {card.level}",
                    color=discord.Color.blurple(),
                )
                if image:
                    embed.set_image(url=image)
                embeds.append(embed)

        await interaction.response.send_message(
            content=f"🎴 {target.mention}'s Gacha Decks",
            embeds=embeds,
        )
