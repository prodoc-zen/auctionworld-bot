from datetime import timedelta

import discord
from discord import app_commands
from sqlalchemy import or_, select

from database.models import AdminUser, AttendanceRecord, utc_now

name        = "weeklyhours"
description = "Check total timed hours for this week"

DEFAULT_WEEKLY_QUOTA_HOURS = 10


def week_start(now):
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def format_duration(total_seconds: float) -> str:
    total_minutes = max(0, int(total_seconds // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


async def get_weekly_seconds(session, discord_id: int, start, now):
    result = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.discord_id == discord_id,
            AttendanceRecord.time_in_at < now,
            or_(
                AttendanceRecord.time_out_at.is_(None),
                AttendanceRecord.time_out_at >= start,
            ),
        )
    )
    records      = result.scalars().all()
    total_seconds = 0
    active_count  = 0

    for record in records:
        session_start = max(record.time_in_at, start)
        session_end   = record.time_out_at or now
        if record.time_out_at is None:
            active_count += 1
        if session_end > session_start:
            total_seconds += (session_end - session_start).total_seconds()

    return total_seconds, active_count


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(member="Pick one admin, or leave blank to list all admin users")
    async def weeklyhours(interaction, member: discord.Member = None):
        now         = utc_now()
        start       = week_start(now)
        quota_hours = int(
            interaction.client.config.get("weekly_quota_hours", DEFAULT_WEEKLY_QUOTA_HOURS)
        )

        async with database.session() as session:
            if member is None:
                result = await session.execute(
                    select(AdminUser)
                    .where(AdminUser.is_active.is_(True))
                    .order_by(AdminUser.discord_id.asc())
                )
                admins = result.scalars().all()

                if not admins:
                    await interaction.response.send_message(
                        "No active admin users are registered yet.", ephemeral=True,
                    )
                    return

                lines = []
                for admin in admins:
                    secs, active = await get_weekly_seconds(session, admin.discord_id, start, now)
                    active_text  = " *(active)*" if active else ""
                    lines.append(f"<@{admin.discord_id}> — {format_duration(secs)}{active_text}")

                embed = discord.Embed(
                    title="Admin Weekly Hours",
                    description="\n".join(lines[:30]),
                    color=discord.Color.blurple(),
                )
                embed.add_field(name="Quota", value=f"{quota_hours}h per week", inline=True)
                embed.set_footer(text=f"Week starts {start.strftime('%Y-%m-%d')} UTC")
                await interaction.response.send_message(embed=embed)
                return

            total_seconds, active_count = await get_weekly_seconds(
                session, member.id, start, now
            )

        quota_seconds    = quota_hours * 3600
        remaining        = max(0, quota_seconds - total_seconds)
        percent          = (
            100 if quota_seconds == 0
            else min(100, round((total_seconds / quota_seconds) * 100))
        )

        embed = discord.Embed(
            title="Weekly Hours",
            description=f"{member.mention}'s attendance total for this week.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Timed",           value=format_duration(total_seconds), inline=True)
        embed.add_field(name="Quota",           value=f"{quota_hours}h",              inline=True)
        embed.add_field(name="Remaining",       value=format_duration(remaining),     inline=True)
        embed.add_field(name="Progress",        value=f"{percent}%",                  inline=True)
        embed.add_field(name="Active Sessions", value=str(active_count),              inline=True)
        embed.set_footer(text=f"Week starts {start.strftime('%Y-%m-%d')} UTC")
        await interaction.response.send_message(embed=embed)
