import discord

name        = "open-ticket"
description = "Reopen a closed ticket"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def open_ticket(interaction):
        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description="This ticket has been reopened by a moderator.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Reopened By", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
