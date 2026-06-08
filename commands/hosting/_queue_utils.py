"""
Shared helpers for the hosting queue commands.
"""
import asyncio
from datetime import timedelta

import discord
from sqlalchemy import select

from database.models import HostingQueueEntry, utc_now

QUEUES = ("Left", "Mid", "Right")

WAITING = "waiting"
ACTIVE  = "active"
DONE    = "done"
SKIPPED = "skipped"

_session_tasks: dict = {}
_grace_tasks:   dict = {}
_panel_messages: set = set()

QUEUE_EMOJIS = {
    "Left":  "🟦",
    "Mid":   "🟩",
    "Right": "🟥",
}


def register_panel_message(channel_id: int, message_id: int):
    _panel_messages.add((channel_id, message_id))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def get_active(session, queue_name: str):
    result = await session.execute(
        select(HostingQueueEntry)
        .where(
            HostingQueueEntry.queue_name == queue_name,
            HostingQueueEntry.status == ACTIVE,
        )
        .order_by(HostingQueueEntry.started_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_next_waiting(session, queue_name: str):
    result = await session.execute(
        select(HostingQueueEntry)
        .where(
            HostingQueueEntry.queue_name == queue_name,
            HostingQueueEntry.status == WAITING,
        )
        .order_by(HostingQueueEntry.joined_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_waiting(session, queue_name: str):
    result = await session.execute(
        select(HostingQueueEntry)
        .where(
            HostingQueueEntry.queue_name == queue_name,
            HostingQueueEntry.status == WAITING,
        )
        .order_by(HostingQueueEntry.joined_at.asc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Startup recovery
# ---------------------------------------------------------------------------

async def recover_active_sessions(client, database):
    now = utc_now()

    async with database.session() as session:
        result = await session.execute(
            select(HostingQueueEntry).where(HostingQueueEntry.status == ACTIVE)
        )
        active_entries = result.scalars().all()

        for entry in active_entries:
            if entry.expires_at is None:
                continue

            remaining_seconds   = (entry.expires_at - now).total_seconds()
            announce_channel_id = resolve_announce_channel_id(client, entry.channel_id)
            if announce_channel_id is None:
                continue

            if remaining_seconds <= 0:
                entry.status       = DONE
                entry.completed_at = now
            else:
                schedule_session_end(
                    client, database,
                    entry.queue_name, entry.id,
                    announce_channel_id, remaining_seconds / 60,
                )

        await session.commit()

    if active_entries:
        client.logger.info("Recovered %d active hosting session(s) after restart.", len(active_entries))


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

def remaining_minutes_text(now, expires_at) -> str:
    if expires_at is None:
        return "--"
    remaining = max(0, int((expires_at - now).total_seconds()))
    minutes, seconds = divmod(remaining, 60)
    return f"{minutes}m {seconds:02d}s"


async def build_queue_embed(database) -> discord.Embed:
    embed = discord.Embed(
        title="🏪 Hosting Queue",
        color=discord.Color.green(),
    )

    async with database.session() as session:
        now = utc_now()

        for queue_name in QUEUES:
            emoji   = QUEUE_EMOJIS.get(queue_name, "⬜")
            active  = await get_active(session, queue_name)
            waiting = await get_waiting(session, queue_name)

            if active:
                host_line = f"🎙️ <@{active.discord_id}>\n⏱️ {remaining_minutes_text(now, active.expires_at)} left"
            else:
                host_line = "✅ Available"

            if waiting:
                queue_lines = "\n".join(
                    f"{i}. <@{e.discord_id}>"
                    for i, e in enumerate(waiting[:8], start=1)
                )
                if len(waiting) > 8:
                    queue_lines += f"\n...+{len(waiting) - 8} more"
            else:
                queue_lines = "*(empty)*"

            embed.add_field(
                name=f"{emoji} {queue_name}",
                value=f"{host_line}\n\n**Queue:**\n{queue_lines}",
                inline=True,
            )

    embed.set_footer(text="Use the buttons below to join, start, or leave.")
    return embed


async def refresh_panel(interaction, database):
    embed = await build_queue_embed(database)
    view  = HostingQueueView(database)
    await interaction.message.edit(embed=embed, view=view)


async def refresh_all_panels(client, database):
    embed = await build_queue_embed(database)
    view  = HostingQueueView(database)
    stale = []

    for channel_id, message_id in list(_panel_messages):
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except Exception:
                stale.append((channel_id, message_id))
                continue
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=embed, view=view)
        except Exception:
            stale.append((channel_id, message_id))

    for key in stale:
        _panel_messages.discard(key)


# ---------------------------------------------------------------------------
# Timer helpers
# ---------------------------------------------------------------------------

def format_minutes(minutes: int) -> str:
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def resolve_announce_channel_id(client, fallback_channel_id=None):
    configured = client.config.get("hosting_announce_channel_id")
    if configured:
        return int(configured)
    return fallback_channel_id


def resolve_timeup_channel_id(client, fallback_channel_id=None):
    configured = client.config.get("hosting_timeup_channel_id")
    if configured:
        return int(configured)
    return resolve_announce_channel_id(client, fallback_channel_id)


def cancel_task(tasks: dict, key):
    task = tasks.pop(key, None)
    if task and not task.done():
        task.cancel()


async def send_channel_message(client, channel_id, message: str):
    if channel_id is None:
        return
    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    await channel.send(message)


async def send_turn_prompt(client, database, channel_id, user_id, queue_name, grace):
    if channel_id is None:
        return
    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    await channel.send(
        f"<@{user_id}> it is your turn for **{queue_name}**."
        f" Press a start button within {format_minutes(grace)}.",
        view=TurnStartPromptView(database),
    )


async def start_hosting_for_user(client, database, queue_name, discord_id, fallback_channel_id=None):
    now                 = utc_now()
    session_minutes     = int(client.config.get("hosting_session_minutes", 60))
    announce_channel_id = resolve_announce_channel_id(client, fallback_channel_id)

    async with database.session() as session:
        active = await get_active(session, queue_name)
        if active is not None:
            return False, f"{queue_name} is already being hosted by <@{active.discord_id}>."

        next_entry = await get_next_waiting(session, queue_name)
        if next_entry is None:
            return False, f"The {queue_name} queue is empty."

        if next_entry.discord_id != discord_id:
            return False, f"It is <@{next_entry.discord_id}>'s turn for {queue_name}."

        next_entry.status     = ACTIVE
        next_entry.started_at = now
        next_entry.expires_at = now + timedelta(minutes=session_minutes)
        next_entry.channel_id = announce_channel_id
        await session.commit()
        entry_id = next_entry.id

    cancel_task(_grace_tasks, (queue_name, entry_id))
    schedule_session_end(client, database, queue_name, entry_id, announce_channel_id, session_minutes)

    await send_channel_message(
        client, announce_channel_id,
        f"<@{discord_id}> started **{queue_name}** hosting. Session: {format_minutes(session_minutes)}.",
    )
    await refresh_all_panels(client, database)
    return True, f"You started {queue_name} hosting. Session: {format_minutes(session_minutes)}."


def schedule_session_end(client, database, queue_name, entry_id, channel_id, minutes):
    cancel_task(_session_tasks, (queue_name, entry_id))
    _session_tasks[(queue_name, entry_id)] = asyncio.create_task(
        _finish_session_after_delay(client, database, queue_name, entry_id, channel_id, minutes)
    )


def schedule_start_grace(client, database, queue_name, entry_id, channel_id, minutes):
    cancel_task(_grace_tasks, (queue_name, entry_id))
    _grace_tasks[(queue_name, entry_id)] = asyncio.create_task(
        _skip_after_grace(client, database, queue_name, entry_id, channel_id, minutes)
    )


async def _finish_session_after_delay(client, database, queue_name, entry_id, channel_id, minutes):
    await asyncio.sleep(minutes * 60)

    next_entry          = None
    finished_discord_id = None

    async with database.session() as session:
        entry = await session.get(HostingQueueEntry, entry_id)
        if entry is None or entry.status != ACTIVE:
            return

        entry.status        = DONE
        entry.completed_at  = utc_now()
        finished_discord_id = entry.discord_id
        await session.commit()

        next_entry = await get_next_waiting(session, queue_name)
        if next_entry is not None:
            next_entry.channel_id = channel_id
            await session.commit()

    timeup_channel_id = resolve_timeup_channel_id(client, channel_id)
    await send_channel_message(
        client, timeup_channel_id,
        f"<@{finished_discord_id}>, your **{queue_name}** hosting session is done.",
    )

    if next_entry is not None:
        grace = int(client.config.get("hosting_start_grace_minutes", 5))
        schedule_start_grace(client, database, queue_name, next_entry.id, channel_id, grace)
        await send_turn_prompt(client, database, channel_id, next_entry.discord_id, queue_name, grace)

    await refresh_all_panels(client, database)


async def _skip_after_grace(client, database, queue_name, entry_id, channel_id, minutes):
    await asyncio.sleep(minutes * 60)

    async with database.session() as session:
        if await get_active(session, queue_name) is not None:
            return

        entry = await session.get(HostingQueueEntry, entry_id)
        if entry is None or entry.status != WAITING:
            return

        entry.status       = SKIPPED
        entry.completed_at = utc_now()
        await session.commit()

        next_entry = await get_next_waiting(session, queue_name)
        if next_entry is not None:
            next_entry.channel_id = channel_id
            await session.commit()

    await send_channel_message(
        client, channel_id,
        f"<@{entry.discord_id}> did not start **{queue_name}** in time and was skipped.",
    )

    if next_entry is not None:
        schedule_start_grace(client, database, queue_name, next_entry.id, channel_id, minutes)
        await send_turn_prompt(client, database, channel_id, next_entry.discord_id, queue_name, minutes)

    await refresh_all_panels(client, database)


# ---------------------------------------------------------------------------
# UI Views
# ---------------------------------------------------------------------------

class HostingQueueView(discord.ui.View):
    def __init__(self, database):
        super().__init__(timeout=None)
        self.database = database

        for index, queue_name in enumerate(QUEUES):
            self.add_item(JoinQueueButton(queue_name,  row=index))
            self.add_item(StartQueueButton(queue_name, row=index))

        self.add_item(LeaveQueueButton(row=3))
        self.add_item(LeaveHostingButton(row=3))
        self.add_item(RefreshQueueButton(row=4))


class JoinQueueButton(discord.ui.Button):
    def __init__(self, queue_name, row):
        super().__init__(
            label=f"Join {queue_name}",
            style=discord.ButtonStyle.primary,
            row=row,
        )
        self.queue_name = queue_name

    async def callback(self, interaction):
        discord_id          = interaction.user.id
        now                 = utc_now()
        announce_channel_id = resolve_announce_channel_id(interaction.client, interaction.channel_id)

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.queue_name == self.queue_name,
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status.in_([WAITING, ACTIVE]),
                )
            )
            if result.scalar_one_or_none() is not None:
                await interaction.response.send_message(
                    f"You are already in the {self.queue_name} queue.", ephemeral=True,
                )
                return

            entry = HostingQueueEntry(
                queue_name=self.queue_name,
                discord_id=discord_id,
                channel_id=announce_channel_id,
                joined_at=now,
            )
            session.add(entry)
            await session.flush()

            active        = await get_active(session, self.queue_name)
            first_waiting = await get_next_waiting(session, self.queue_name)
            should_prompt = active is None and first_waiting and first_waiting.id == entry.id
            next_entry_id = entry.id
            await session.commit()

        await interaction.response.send_message(
            f"You joined the **{self.queue_name}** queue.", ephemeral=True,
        )
        await refresh_panel(interaction, self.view.database)

        if should_prompt:
            grace = int(interaction.client.config.get("hosting_start_grace_minutes", 5))
            schedule_start_grace(
                interaction.client, self.view.database,
                self.queue_name, next_entry_id,
                announce_channel_id, grace,
            )
            await send_turn_prompt(
                interaction.client, self.view.database,
                announce_channel_id, discord_id,
                self.queue_name, grace,
            )

        await refresh_all_panels(interaction.client, self.view.database)


class StartQueueButton(discord.ui.Button):
    def __init__(self, queue_name, row):
        super().__init__(
            label=f"Start {queue_name}",
            style=discord.ButtonStyle.success,
            row=row,
        )
        self.queue_name = queue_name

    async def callback(self, interaction):
        ok, message = await start_hosting_for_user(
            interaction.client, self.view.database,
            self.queue_name, interaction.user.id,
            interaction.channel_id,
        )
        await interaction.response.send_message(message, ephemeral=True)
        await refresh_panel(interaction, self.view.database)


class LeaveQueueButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="Leave Queue", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction):
        discord_id = interaction.user.id
        removed    = 0

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status == WAITING,
                )
            )
            for entry in result.scalars().all():
                entry.status       = SKIPPED
                entry.completed_at = utc_now()
                removed += 1
            await session.commit()

        await interaction.response.send_message(
            f"Removed you from {removed} queue(s).", ephemeral=True,
        )
        await refresh_panel(interaction, self.view.database)
        await refresh_all_panels(interaction.client, self.view.database)


class LeaveHostingButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="Leave Hosting", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction):
        discord_id = interaction.user.id
        now        = utc_now()
        ended      = []

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status == ACTIVE,
                )
            )
            active_entries = result.scalars().all()

            if not active_entries:
                await interaction.response.send_message("You are not currently hosting.", ephemeral=True)
                return

            for entry in active_entries:
                entry.status       = DONE
                entry.completed_at = now
                ended.append((entry.queue_name, entry.id, resolve_announce_channel_id(interaction.client, entry.channel_id)))
            await session.commit()

        for queue_name, entry_id, announce_channel_id in ended:
            cancel_task(_session_tasks, (queue_name, entry_id))

            async with self.view.database.session() as session:
                next_entry = await get_next_waiting(session, queue_name)
                if next_entry is not None:
                    next_entry.channel_id = announce_channel_id
                    await session.commit()

            await send_channel_message(
                interaction.client, announce_channel_id,
                f"<@{discord_id}> ended **{queue_name}** hosting early.",
            )

            if next_entry is not None:
                grace = int(interaction.client.config.get("hosting_start_grace_minutes", 5))
                schedule_start_grace(interaction.client, self.view.database, queue_name, next_entry.id, announce_channel_id, grace)
                await send_turn_prompt(interaction.client, self.view.database, announce_channel_id, next_entry.discord_id, queue_name, grace)

        await interaction.response.send_message("Ended your active hosting session(s).", ephemeral=True)
        await refresh_panel(interaction, self.view.database)
        await refresh_all_panels(interaction.client, self.view.database)


class RefreshQueueButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="Refresh", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        await refresh_all_panels(interaction.client, self.view.database)
        await refresh_panel(interaction, self.view.database)
        await interaction.followup.send("Refreshed.", ephemeral=True)


class TurnStartPromptView(discord.ui.View):
    def __init__(self, database):
        super().__init__(timeout=300)
        self.database = database

    @discord.ui.button(label="Start Left",  style=discord.ButtonStyle.success)
    async def start_left(self, interaction, button):
        ok, message = await start_hosting_for_user(interaction.client, self.database, "Left",  interaction.user.id, interaction.channel_id)
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Start Mid",   style=discord.ButtonStyle.success)
    async def start_mid(self, interaction, button):
        ok, message = await start_hosting_for_user(interaction.client, self.database, "Mid",   interaction.user.id, interaction.channel_id)
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Start Right", style=discord.ButtonStyle.success)
    async def start_right(self, interaction, button):
        ok, message = await start_hosting_for_user(interaction.client, self.database, "Right", interaction.user.id, interaction.channel_id)
        await interaction.response.send_message(message, ephemeral=True)
