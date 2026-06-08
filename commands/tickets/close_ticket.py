import discord

name        = "close-ticket"
description = "Close this ticket"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def close_ticket(interaction):
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description="This ticket has been closed by a moderator.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Closed By", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
