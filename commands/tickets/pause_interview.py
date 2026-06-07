import discord

name        = "pause-interview"
description = "Pause an interview in this ticket"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def pause_interview(interaction):
        embed = discord.Embed(
            title="⏸️ Interview Paused",
            description="This interview has been paused by a moderator. Please wait until it is resumed.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Paused By", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
