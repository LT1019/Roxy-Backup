import os
import discord
from discord.ext import commands
from database import RoxyDatabase, OPTED_OUT

# Optional public links to the full documents (PRIVACY.md / TERMS.md hosted somewhere) - shown as buttons on rr privacy
DOCUMENT_LINKS = [
    (label, url) for label, url in (
        ('📄 Privacy Policy', os.getenv('PRIVACY_URL', '').strip()),
        ('📜 Terms of Service', os.getenv('TERMS_URL', '').strip()),
    ) if url.startswith('https://')
]


class ConfirmDelete(discord.ui.View):
    """Confirm/Cancel for deleting your own data - only the person who asked can press it"""

    def __init__(self, owner_id: int):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This isn't your request.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label='🗑️ Yes, delete my data', style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        self.confirmed = True
        await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content="Cancelled - nothing was deleted.", embed=None, view=None)
        self.stop()


class RoxyPrivacy(commands.Cog):
    """Privacy controls: what Roxy stores, opting out, and deleting your data"""

    def __init__(self, bot):
        self.bot = bot
        self.db = RoxyDatabase()

    def stop_live_tracking(self, user_id: int):
        """Forget any session Roxy is currently tracking for this user"""
        self.bot.active_sessions.pop(user_id, None)
        self.bot.active_listening.pop(user_id, None)

    async def confirm(self, ctx, title: str, description: str) -> bool:
        view = ConfirmDelete(ctx.author.id)
        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        message = await ctx.send(embed=embed, view=view)
        if await view.wait():
            await message.edit(content="⌛ Timed out - nothing was deleted.", embed=None, view=None)
        return view.confirmed

    @commands.command(name='privacy', aliases=['policy'])
    async def privacy(self, ctx):
        """What Roxy stores about you and how to control it"""
        embed = discord.Embed(
            title="🔒 Roxy Privacy",
            description="Roxy is a stats bot - here is exactly what she keeps and how you stay in control.",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="📦 What Roxy stores",
            value="• Your Discord ID, username and display name\n• **How many** messages you send (never what they say)\n• Games shown in your status and how long you played\n• Spotify songs shown in your status and how long you listened\n• Your level, XP and achievements",
            inline=False
        )
        embed.add_field(
            name="🚫 What Roxy never does",
            value="• Store or read the content of your messages\n• Sell or share your data with anyone\n• Use your data for ads or anything besides Roxy's features\n• Track you after you opt out",
            inline=False
        )
        embed.add_field(
            name="🎛️ Your controls",
            value="`rr mydata` - See what is stored about you\n`rr deletemydata` - Delete everything (tracking continues)\n`rr optout` - Delete everything **and** stop tracking you\n`rr optin` - Start tracking again",
            inline=False
        )
        embed.set_footer(text="Questions? Use the Support button under rr help")

        view = None
        if DOCUMENT_LINKS:
            view = discord.ui.View()
            for label, url in DOCUMENT_LINKS:
                view.add_item(discord.ui.Button(label=label, url=url))
        await ctx.send(embed=embed, view=view)

    @commands.command(name='mydata')
    async def my_data(self, ctx):
        """Show how much data Roxy holds about you"""
        if ctx.author.id in OPTED_OUT:
            await ctx.send("🔒 You've opted out - Roxy stores **nothing** about you. Use `rr optin` to be tracked again.")
            return

        summary = await self.db.get_user_data_summary(ctx.author.id)
        stats = await self.db.get_user_stats(ctx.author.id)

        embed = discord.Embed(title=f"📦 Data stored about {ctx.author.display_name}", color=discord.Color.purple())
        if stats:
            embed.add_field(
                name="👤 Profile",
                value=f"**Messages counted:** {stats[4]:,}\n**Gaming time:** {stats[5] // 3600}h {(stats[5] % 3600) // 60}m\n**Listening time:** {stats[10] // 3600}h {(stats[10] % 3600) // 60}m\n**Level:** {stats[8]} ({stats[9]:,} XP)",
                inline=False
            )
        embed.add_field(
            name="🗂️ Records",
            value=f"**Gaming sessions:** {summary['game_sessions']:,}\n**Listening sessions:** {summary['listening_sessions']:,}\n**Achievements:** {summary['achievements']:,}",
            inline=False
        )
        embed.set_footer(text="rr deletemydata to erase it • rr optout to erase it and stop tracking • rr privacy for details")
        await ctx.send(embed=embed)

    @commands.command(name='deletemydata')
    async def delete_my_data(self, ctx):
        """Delete everything Roxy stores about you (tracking continues from zero)"""
        confirmed = await self.confirm(
            ctx, "🗑️ Delete your data?",
            "This permanently deletes your level, XP, message count, gaming and listening history and achievements.\n\n"
            "**This can't be undone.** Roxy will keep tracking new activity from zero - use `rr optout` to stop tracking too."
        )
        if not confirmed:
            return

        self.stop_live_tracking(ctx.author.id)
        deleted = await self.db.delete_user_data(ctx.author.id)
        await ctx.send(f"✅ Deleted your data ({sum(deleted.values()):,} records). You're starting fresh, {ctx.author.mention}.")

    @commands.command(name='optout')
    async def opt_out(self, ctx):
        """Stop Roxy from tracking you and delete your data"""
        if ctx.author.id in OPTED_OUT:
            await ctx.send("🔒 You're already opted out. Use `rr optin` to be tracked again.")
            return

        confirmed = await self.confirm(
            ctx, "🔒 Opt out of Roxy?",
            "Roxy will **stop tracking** your messages, games and music in every server, and **permanently delete** "
            "your level, XP, history and achievements.\n\n**This can't be undone** - if you opt in again later you start from zero."
        )
        if not confirmed:
            return

        self.stop_live_tracking(ctx.author.id)
        deleted = await self.db.opt_out(ctx.author.id)
        await ctx.send(f"✅ You're opted out, {ctx.author.mention}. Deleted {sum(deleted.values()):,} records - Roxy won't track you anymore. Use `rr optin` anytime to come back.")

    @commands.command(name='optin')
    async def opt_in(self, ctx):
        """Let Roxy track you again after opting out"""
        if await self.db.opt_in(ctx.author.id):
            await ctx.send(f"✅ Welcome back, {ctx.author.mention}! Roxy is tracking your activity again, starting from zero.")
        else:
            await ctx.send("ℹ️ You weren't opted out - Roxy is already tracking your activity.")


async def setup(bot):
    await bot.add_cog(RoxyPrivacy(bot))
    print("🔒 Roxy's Privacy cog loaded!")
