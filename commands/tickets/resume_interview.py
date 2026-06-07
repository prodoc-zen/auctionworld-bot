import discord

name        = "resume-interview"
description = "Resume a paused interview in this ticket"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def resume_interview(interaction):
        embed = discord.Embed(
            title="▶️ Interview Resumed",
            description="This interview has been resumed. You may continue.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Resumed By", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
