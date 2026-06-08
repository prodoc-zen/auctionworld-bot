from datetime import timedelta

import discord
from discord import app_commands
from sqlalchemy import select

from database.models import AdminProfile, AttendanceRecord, User, format_earnings, from_wls, to_wls, utc_now

name        = "profile"
description = "View an admin's profile"


def week_start(now):
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def format_duration(total_seconds: float) -> str:
    total_minutes = max(0, int(total_seconds // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


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
                    f"{target.mention} does not have an admin profile.", ephemeral=True,
                )
                return

            user = await session.get(User, discord_id)

            result = await session.execute(
                select(AttendanceRecord).where(AttendanceRecord.discord_id == discord_id)
            )
            records = result.scalars().all()

        # Time worked
        weekly_secs = 0
        total_secs  = 0
        weekly_wls  = 0
        total_wls   = 0

        for record in records:
            session_end = record.time_out_at or now
            duration    = max(0, (session_end - record.time_in_at).total_seconds())
            total_secs += duration
            total_wls  += to_wls(record.bgls, record.dls, record.wls)

            if record.time_in_at >= start:
                weekly_secs += duration
                weekly_wls  += to_wls(record.bgls, record.dls, record.wls)

        weekly_earn = format_earnings(*from_wls(weekly_wls))
        total_earn  = format_earnings(*from_wls(total_wls))

        embed = discord.Embed(
            title=f"Admin Profile  {admin_profile.id}",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💬 Discord",          value=target.mention,                            inline=True)
        embed.add_field(name="🌿 GT Name",          value=admin_profile.gt_name,                    inline=True)
        embed.add_field(name="👤 Role",             value=admin_profile.role,                       inline=True)
        embed.add_field(name="🪙 Jennies",          value=f"{user.jennies if user else 0} jennies",  inline=True)
        embed.add_field(name="🎫 Priority Tickets", value=str(admin_profile.priority_tickets),      inline=True)
        embed.add_field(
            name="⏱️ Time Worked",
            value=f"Weekly: {format_duration(weekly_secs)}\nTotal: {format_duration(total_secs)}",
            inline=True,
        )
        embed.add_field(
            name="💰 Earnings",
            value=f"Weekly: {weekly_earn}\nTotal: {total_earn}",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)
