from commands.hosting._queue_utils import HostingQueueView, build_queue_embed, register_panel_message

name        = "hosting"
description = "Open the hosting queue panel"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def hosting(interaction):
        embed = await build_queue_embed(database)
        await interaction.response.send_message(
            embed=embed,
            view=HostingQueueView(database),
        )
        message = await interaction.original_response()
        register_panel_message(message.channel.id, message.id)
