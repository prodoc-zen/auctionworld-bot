import asyncio
from datetime import timedelta

import discord
from sqlalchemy import select

from database.models import HostingQueueEntry, utc_now


name = "hosting"
description = "Open the hosting queue panel"

QUEUES = ("Left", "Mid", "Right")
WAITING = "waiting"
ACTIVE = "active"
DONE = "done"
SKIPPED = "skipped"

_session_tasks = {}
_grace_tasks = {}


def format_minutes(minutes):
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


async def get_active(session, queue_name):
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


async def get_next_waiting(session, queue_name):
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


async def get_waiting(session, queue_name):
    result = await session.execute(
        select(HostingQueueEntry)
        .where(
            HostingQueueEntry.queue_name == queue_name,
            HostingQueueEntry.status == WAITING,
        )
        .order_by(HostingQueueEntry.joined_at.asc())
    )
    return result.scalars().all()


async def build_queue_embed(database):
    embed = discord.Embed(
        title="Hosting Queue",
        description="Join a lane, then press Start when it is your turn.",
        color=discord.Color.green(),
    )

    async with database.session() as session:
        for queue_name in QUEUES:
            active = await get_active(session, queue_name)
            waiting = await get_waiting(session, queue_name)

            if active:
                active_text = f"Hosting: <@{active.discord_id}>"
                if active.expires_at:
                    active_text += f"\nEnds <t:{int(active.expires_at.timestamp())}:R>"
            else:
                active_text = "No active host"

            if waiting:
                waiting_text = "\n".join(
                    f"{index}. <@{entry.discord_id}>"
                    for index, entry in enumerate(waiting[:8], start=1)
                )
                if len(waiting) > 8:
                    waiting_text += f"\n...and {len(waiting) - 8} more"
            else:
                waiting_text = "Queue is empty"

            embed.add_field(
                name=queue_name,
                value=f"{active_text}\n\n{waiting_text}",
                inline=True,
            )

    return embed


async def refresh_panel(interaction, database):
    embed = await build_queue_embed(database)
    view = HostingQueueView(database)
    await interaction.message.edit(embed=embed, view=view)


def cancel_task(tasks, key):
    task = tasks.pop(key, None)
    if task and not task.done():
        task.cancel()


def schedule_session_end(client, database, queue_name, entry_id, channel_id, minutes):
    cancel_task(_session_tasks, (queue_name, entry_id))
    _session_tasks[(queue_name, entry_id)] = asyncio.create_task(
        finish_session_after_delay(client, database, queue_name, entry_id, channel_id, minutes)
    )


def schedule_start_grace(client, database, queue_name, entry_id, channel_id, minutes):
    cancel_task(_grace_tasks, (queue_name, entry_id))
    _grace_tasks[(queue_name, entry_id)] = asyncio.create_task(
        skip_after_grace(client, database, queue_name, entry_id, channel_id, minutes)
    )


async def send_channel_message(client, channel_id, message):
    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    await channel.send(message)


async def finish_session_after_delay(client, database, queue_name, entry_id, channel_id, minutes):
    await asyncio.sleep(minutes * 60)

    next_entry = None
    async with database.session() as session:
        entry = await session.get(HostingQueueEntry, entry_id)
        if entry is None or entry.status != ACTIVE:
            return

        entry.status = DONE
        entry.completed_at = utc_now()
        await session.commit()

        next_entry = await get_next_waiting(session, queue_name)
        if next_entry is not None:
            next_entry.channel_id = channel_id
            await session.commit()

    await send_channel_message(
        client,
        channel_id,
        f"<@{entry.discord_id}>, your {queue_name} hosting session is done.",
    )

    if next_entry is not None:
        grace_minutes = int(client.config.get("hosting_start_grace_minutes", 5))
        schedule_start_grace(client, database, queue_name, next_entry.id, channel_id, grace_minutes)
        await send_channel_message(
            client,
            channel_id,
            f"<@{next_entry.discord_id}>, it is your turn for {queue_name}. "
            f"Press **Start {queue_name}** within {format_minutes(grace_minutes)}.",
        )


async def skip_after_grace(client, database, queue_name, entry_id, channel_id, minutes):
    await asyncio.sleep(minutes * 60)

    async with database.session() as session:
        active = await get_active(session, queue_name)
        if active is not None:
            return

        entry = await session.get(HostingQueueEntry, entry_id)
        if entry is None or entry.status != WAITING:
            return

        entry.status = SKIPPED
        entry.completed_at = utc_now()
        await session.commit()

        next_entry = await get_next_waiting(session, queue_name)
        if next_entry is not None:
            next_entry.channel_id = channel_id
            await session.commit()

    await send_channel_message(
        client,
        channel_id,
        f"<@{entry.discord_id}> did not start {queue_name} in time and was removed from the queue.",
    )

    if next_entry is not None:
        schedule_start_grace(client, database, queue_name, next_entry.id, channel_id, minutes)
        await send_channel_message(
            client,
            channel_id,
            f"<@{next_entry.discord_id}>, it is your turn for {queue_name}. "
            f"Press **Start {queue_name}** within {format_minutes(minutes)}.",
        )


class HostingQueueView(discord.ui.View):
    def __init__(self, database):
        super().__init__(timeout=900)
        self.database = database

        for index, queue_name in enumerate(QUEUES):
            self.add_item(JoinQueueButton(queue_name, row=index))
            self.add_item(StartQueueButton(queue_name, row=index))

        self.add_item(LeaveQueueButton(row=3))
        self.add_item(RefreshQueueButton(row=3))


class JoinQueueButton(discord.ui.Button):
    def __init__(self, queue_name, row):
        super().__init__(
            label=f"Join {queue_name}",
            style=discord.ButtonStyle.primary,
            row=row,
        )
        self.queue_name = queue_name

    async def callback(self, interaction):
        discord_id = interaction.user.id
        now = utc_now()
        should_prompt_start = False
        next_entry_id = None

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.queue_name == self.queue_name,
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status.in_([WAITING, ACTIVE]),
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                await interaction.response.send_message(
                    f"{interaction.user.mention}, you are already in {self.queue_name}.",
                    ephemeral=True,
                )
                return

            entry = HostingQueueEntry(
                queue_name=self.queue_name,
                discord_id=discord_id,
                channel_id=interaction.channel_id,
                joined_at=now,
            )
            session.add(entry)
            await session.flush()

            active = await get_active(session, self.queue_name)
            first_waiting = await get_next_waiting(session, self.queue_name)
            should_prompt_start = active is None and first_waiting and first_waiting.id == entry.id
            next_entry_id = entry.id
            await session.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention}, you joined the {self.queue_name} hosting queue.",
            ephemeral=True,
        )
        await refresh_panel(interaction, self.view.database)

        if should_prompt_start:
            grace_minutes = int(interaction.client.config.get("hosting_start_grace_minutes", 5))
            schedule_start_grace(
                interaction.client,
                self.view.database,
                self.queue_name,
                next_entry_id,
                interaction.channel_id,
                grace_minutes,
            )
            await interaction.channel.send(
                f"{interaction.user.mention}, {self.queue_name} is ready. "
                f"Press **Start {self.queue_name}** within {format_minutes(grace_minutes)}."
            )


class StartQueueButton(discord.ui.Button):
    def __init__(self, queue_name, row):
        super().__init__(
            label=f"Start {queue_name}",
            style=discord.ButtonStyle.success,
            row=row,
        )
        self.queue_name = queue_name

    async def callback(self, interaction):
        discord_id = interaction.user.id
        now = utc_now()
        session_minutes = int(interaction.client.config.get("hosting_session_minutes", 60))

        async with self.view.database.session() as session:
            active = await get_active(session, self.queue_name)
            if active is not None:
                await interaction.response.send_message(
                    f"{self.queue_name} is already being hosted by <@{active.discord_id}>.",
                    ephemeral=True,
                )
                return

            next_entry = await get_next_waiting(session, self.queue_name)
            if next_entry is None:
                await interaction.response.send_message(
                    f"The {self.queue_name} queue is empty.",
                    ephemeral=True,
                )
                return

            if next_entry.discord_id != discord_id:
                await interaction.response.send_message(
                    f"It is <@{next_entry.discord_id}>'s turn for {self.queue_name}.",
                    ephemeral=True,
                )
                return

            next_entry.status = ACTIVE
            next_entry.started_at = now
            next_entry.expires_at = now + timedelta(minutes=session_minutes)
            next_entry.channel_id = interaction.channel_id
            await session.commit()
            entry_id = next_entry.id

        cancel_task(_grace_tasks, (self.queue_name, entry_id))
        schedule_session_end(
            interaction.client,
            self.view.database,
            self.queue_name,
            entry_id,
            interaction.channel_id,
            session_minutes,
        )

        await interaction.response.send_message(
            f"{interaction.user.mention} started {self.queue_name} hosting. "
            f"Session length: {format_minutes(session_minutes)}."
        )
        await refresh_panel(interaction, self.view.database)


class LeaveQueueButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(
            label="Leave Queue",
            style=discord.ButtonStyle.danger,
            row=row,
        )

    async def callback(self, interaction):
        discord_id = interaction.user.id
        removed = 0

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status == WAITING,
                )
            )
            entries = result.scalars().all()
            for entry in entries:
                entry.status = SKIPPED
                entry.completed_at = utc_now()
                removed += 1

            await session.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention}, removed you from {removed} waiting queue(s).",
            ephemeral=True,
        )
        await refresh_panel(interaction, self.view.database)


class RefreshQueueButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(
            label="Refresh",
            style=discord.ButtonStyle.secondary,
            row=row,
        )

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        await refresh_panel(interaction, self.view.database)
        await interaction.followup.send("Queue panel refreshed.", ephemeral=True)


def register(tree, database):
    @tree.command(name=name, description=description)
    async def hosting(interaction):
        embed = await build_queue_embed(database)
        await interaction.response.send_message(
            embed=embed,
            view=HostingQueueView(database),
        )
