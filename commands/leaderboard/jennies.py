from datetime import timedelta

import discord
from discord import app_commands
from sqlalchemy import desc, select

from database.models import AttendanceRecord, User, from_wls, to_wls, utc_now

name        = "leaderboard"
description = "View server leaderboards"

BOARD_CHOICES = [
    app_commands.Choice(name="Jennies",      value="jennies"),
    app_commands.Choice(name="Time Worked",  value="time"),
    app_commands.Choice(name="Earnings",     value="earnings"),
]


def week_start(now):
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def format_duration(total_seconds: float) -> str:
    total_minutes = max(0, int(total_seconds // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(board="Which leaderboard to view")
    @app_commands.choices(board=BOARD_CHOICES)
    async def leaderboard(interaction, board: app_commands.Choice[str] = None):
        board_value = board.value if board else "jennies"
        now         = utc_now()

        async with database.session() as session:
            if board_value == "jennies":
                result = await session.execute(
                    select(User).order_by(desc(User.jennies)).limit(10)
                )
                users = result.scalars().all()

                if not users:
                    await interaction.response.send_message("No data yet.", ephemeral=True)
                    return

                lines = [
                    f"{i}. <@{u.discord_id}> — **{u.jennies} Jennies**"
                    for i, u in enumerate(users, 1)
                ]
                embed = discord.Embed(title="🪙 Jennies Leaderboard", color=discord.Color.gold())
                embed.description = "\n".join(lines)

            elif board_value == "time":
                result = await session.execute(select(AttendanceRecord))
                records = result.scalars().all()

                time_by_user = {}
                for r in records:
                    end      = r.time_out_at or now
                    duration = max(0, (end - r.time_in_at).total_seconds())
                    time_by_user[r.discord_id] = time_by_user.get(r.discord_id, 0) + duration

                top = sorted(time_by_user.items(), key=lambda x: x[1], reverse=True)[:10]
                if not top:
                    await interaction.response.send_message("No data yet.", ephemeral=True)
                    return

                lines = [
                    f"{i}. <@{uid}> — **{format_duration(secs)}**"
                    for i, (uid, secs) in enumerate(top, 1)
                ]
                embed = discord.Embed(title="⏱️ Time Worked Leaderboard", color=discord.Color.blurple())
                embed.description = "\n".join(lines)

            elif board_value == "earnings":
                result = await session.execute(select(AttendanceRecord))
                records = result.scalars().all()

                earn_by_user = {}
                for r in records:
                    earn_by_user[r.discord_id] = earn_by_user.get(r.discord_id, 0) + to_wls(r.bgls, r.dls, r.wls)

                top = sorted(earn_by_user.items(), key=lambda x: x[1], reverse=True)[:10]
                if not top:
                    await interaction.response.send_message("No data yet.", ephemeral=True)
                    return

                from database.models import format_earnings
                lines = [
                    f"{i}. <@{uid}> — **{format_earnings(*from_wls(wls))}**"
                    for i, (uid, wls) in enumerate(top, 1)
                ]
                embed = discord.Embed(title="💰 Earnings Leaderboard", color=discord.Color.green())
                embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed)
