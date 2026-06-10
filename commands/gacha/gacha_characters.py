import discord
from sqlalchemy import select
from database.models import GachaCard
from commands.gacha._gacha_utils import STAR_EMOJIS

name        = "gacha-characters"
description = "View your gacha character collection"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def gacha_characters(interaction):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(
                select(GachaCard)
                .where(GachaCard.discord_id == discord_id)
                .order_by(GachaCard.rarity.desc(), GachaCard.character_name.asc())
            )
            cards = result.scalars().all()

        if not cards:
            await interaction.response.send_message(
                "You have no characters yet! Use `/gacha-single` or `/gacha-multi` to pull.",
                ephemeral=True,
            )
            return

        lines_by_rarity = {4: [], 3: [], 2: [], 1: []}
        for card in cards:
            lines_by_rarity[card.rarity].append(
                f"**{card.character_name}** (Lv.{card.level})"
            )

        embed = discord.Embed(title=f"🎴 {interaction.user.display_name}'s Collection", color=discord.Color.purple())
        for rarity in [4, 3, 2, 1]:
            if lines_by_rarity[rarity]:
                embed.add_field(
                    name=f"{STAR_EMOJIS[rarity]} {rarity}-Star",
                    value="\n".join(lines_by_rarity[rarity]),
                    inline=False,
                )

        embed.set_footer(text=f"Total: {len(cards)} characters")
        await interaction.response.send_message(embed=embed)
