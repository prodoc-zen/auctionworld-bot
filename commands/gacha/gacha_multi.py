import discord
from sqlalchemy import select
from database.models import GachaCard, User
from commands.gacha._gacha_utils import pull_many, PULL_COST, STAR_EMOJIS, RARITY_COLORS, MAX_LEVEL

name        = "gacha-multi"
description = "Pull 10 gacha characters (1200 Jennies)"

MULTI_COUNT = 10
MULTI_COST  = PULL_COST * MULTI_COUNT


def register(tree, database):
    @tree.command(name=name, description=description)
    async def gacha_multi(interaction):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == discord_id))
            user   = result.scalar_one_or_none()

            if user is None:
                user = User(discord_id=discord_id, jennies=2000)
                session.add(user)
                await session.flush()

            if user.jennies < MULTI_COST:
                await interaction.response.send_message(
                    f"You need **{MULTI_COST} Jennies** to pull 10. You have **{user.jennies}**.",
                    ephemeral=True,
                )
                return

            pulls     = pull_many(MULTI_COUNT)
            user.jennies -= MULTI_COST
            lines     = []

            for character, rarity in pulls:
                stars = STAR_EMOJIS[rarity]
                dup_result = await session.execute(
                    select(GachaCard).where(
                        GachaCard.discord_id == discord_id,
                        GachaCard.character_name == character,
                    )
                )
                existing = dup_result.scalar_one_or_none()

                if existing is not None and existing.level < MAX_LEVEL:
                    existing.level += 1
                    lines.append(f"{stars} **{character}** ✨ Lv.{existing.level}")
                elif existing is None:
                    card = GachaCard(discord_id=discord_id, character_name=character, rarity=rarity)
                    session.add(card)
                    lines.append(f"{stars} **{character}** 🆕")
                else:
                    lines.append(f"{stars} **{character}** (max level)")

            await session.commit()

        embed = discord.Embed(title="🎴 10-Pull Results!", color=discord.Color.purple())
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Cost: {MULTI_COST} Jennies | Balance: {user.jennies} Jennies")

        await interaction.response.send_message(embed=embed)
