from datetime import timedelta

import discord
from discord import app_commands
from sqlalchemy import or_, select, func

from database.models import AdminProfile, AttendanceRecord, User, utc_now

name        = "profile"
description = "View an admin's profile"


def week_start(now):
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def format_duration(total_seconds: float) -> str:
    total_minutes = max(0, int(total_seconds // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


async def get_records(session, discord_id, start, now):
    result = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.discord_id == discord_id,
        )
    )
    return result.scalars().all()


def calculate_time(records, start, now, weekly=True):
    total_seconds = 0
    for record in records:
        if weekly and record.time_in_at < start:
            continue
        session_start = record.time_in_at if not weekly else max(record.time_in_at, start)
        session_end   = record.time_out_at or now
        if session_end > session_start:
            total_seconds += (session_end - session_start).total_seconds()
    return total_seconds


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(member="The admin to view (leave blank for yourself)")
    async def profile(interaction, member: discord.Member = None):
        target     = member or interaction.user
        discord_id = target.id
        now        = utc_now()
        start      = week_start(now)

        async with database.session() as session:
            admin_profile = await session.get(AdminProfile, discord_id)

            if admin_profile is None:
                await interaction.response.send_message(
                    f"{target.mention} does not have an admin profile.",
                    ephemeral=True,
                )
                return

            user    = await session.get(User, discord_id)
            records = await get_records(session, discord_id, start, now)

        weekly_secs  = calculate_time(records, start, now, weekly=True)
        total_secs   = calculate_time(records, start, now, weekly=False)

        # Calculate earnings
        weekly_earnings = [r.earnings for r in records if r.earnings and r.time_in_at >= start]
        total_earnings  = [r.earnings for r in records if r.earnings]
        weekly_earn_text = "\n".join(weekly_earnings) if weekly_earnings else "None"
        total_earn_text  = f"{len(total_earnings)} session(s)" if total_earnings else "None"

        embed = discord.Embed(
            title=f"Admin Profile  {admin_profile.id}",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💬 Discord",          value=target.mention,                           inline=True)
        embed.add_field(name="🌿 GT Name",          value=admin_profile.gt_name,                   inline=True)
        embed.add_field(name="👤 Role",             value=admin_profile.role,                      inline=True)
        embed.add_field(name="🪙 Jennies",          value=f"{user.jennies if user else 0} jennies", inline=True)
        embed.add_field(name="🎫 Priority Tickets", value=str(admin_profile.priority_tickets),     inline=True)
        embed.add_field(
            name="⏱️ Time Worked",
            value=f"Weekly: {format_duration(weekly_secs)}\nTotal: {format_duration(total_secs)}",
            inline=True,
        )
        embed.add_field(
            name="💰 Earnings",
            value=f"Weekly: {weekly_earn_text}\nTotal: {total_earn_text}",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)
