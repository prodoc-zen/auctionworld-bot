name        = "ping"
description = "Check whether the bot is online"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def ping(interaction):
        latency_ms = round(interaction.client.latency * 1000)
        await interaction.response.send_message(f"Pong! {latency_ms}ms")
