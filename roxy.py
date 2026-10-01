import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import random
import aiosqlite
import time
import psutil
from datetime import datetime, timezone
from dotenv import load_dotenv
from database import RoxyDatabase
from config import ADMIN_USER_ID, LINK_BUTTONS, APP_ACTIVITIES, is_admin, is_admin_id, is_server_admin
from patreon import xp_multiplier, get_patrons, get_patron_tier

# Load Roxy's configuration
load_dotenv()

# Roxy's personality and intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

def get_prefix(bot, message):
    """Roxy's prefix is "rr" - "rr help" or "rrhelp", any capitalization (phones auto-capitalize "Rr")"""
    for prefix in ('rr ', 'rr'):
        if message.content[:len(prefix)].lower() == prefix:
            return message.content[:len(prefix)]  # Exact text as typed, so it always matches
    return 'rr '

class RoxyBot(commands.Bot):
    """Roxy - Your friendly Discord stats bot"""
    
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            case_insensitive=True,
            intents=intents,
            help_command=None
        )
        self.db = RoxyDatabase()
        self.active_sessions = {}  # Gaming sessions
        self.active_listening = {}  # Music listening sessions
        self.active_apps = {}  # Non-game app sessions (VS Code, YouTube, ...)
        self.active_voice = {}  # Voice sessions: user_id -> guild_id of the call
        self.start_time: float = 0.0  # Add start_time attribute with type hint
        self.custom_status = None  # Set by rr setstatus - pauses the rotating status

    async def setup_hook(self):
        """Roxy's startup setup"""
        await self.db.init_db()

        # Sessions left open by a crash/restart have no known end time - discard them
        games, listens = await self.db.discard_unfinished_sessions()
        if games or listens:
            print(f"🧹 Discarded {games} unfinished gaming and {listens} unfinished listening sessions from last run")

        await self.load_extension('cogs.stats')
        await self.load_extension('cogs.admin')  # Load admin cog
        print("🤖 Roxy's cogs loaded successfully!")

        # Register slash commands (/dbstats, /logs) with Discord
        try:
            synced = await self.tree.sync()
            print(f"🔗 Synced {len(synced)} slash command(s)")
        except Exception as e:
            print(f"❌ Failed to sync slash commands: {e}")

# Initialize Roxy
roxy = RoxyBot()

# Store bot start time for uptime calculation
@roxy.event
async def on_ready():
    """Roxy comes online!"""
    # on_ready also fires after reconnects - only record the first start for uptime
    if not roxy.start_time:
        roxy.start_time = time.time()

    print(f'🌟 {roxy.user} is now online and ready!')
    print(f'📊 Roxy is active in {len(roxy.guilds)} servers')
    print(f'👥 Watching over {len(roxy.users)} users')

    # Find admin user (if needed for display purposes)
    admin_user = roxy.get_user(ADMIN_USER_ID)
    if admin_user:
        print(f'👑 Admin: {admin_user} ({ADMIN_USER_ID})')
    else:
        print(f'⚠️ Admin user {ADMIN_USER_ID} not found')

    # Pick up everyone already playing/listening, and close sessions that ended while offline
    synced = set()
    for guild in roxy.guilds:
        for member in guild.members:
            if member.bot or member.id in synced:
                continue
            synced.add(member.id)
            try:
                await sync_member_activity(member)
            except Exception as e:
                print(f"❌ Error syncing activity for {member}: {e}")
    # Everyone already in a voice call (checked per server - a call can be in any of them)
    for guild in roxy.guilds:
        for channel in guild.voice_channels + guild.stage_channels:
            for member in channel.members:
                if not member.bot:
                    try:
                        await sync_member_voice(member, member.voice)
                    except Exception as e:
                        print(f"❌ Error syncing voice for {member}: {e}")
    print(f"🔄 Synced activity: {len(roxy.active_sessions)} gaming, {len(roxy.active_listening)} listening, {len(roxy.active_apps)} apps, {len(roxy.active_voice)} in voice")

    # Start Roxy's background tasks (already running after a reconnect)
    if not update_roxy_status.is_running():
        activity = discord.Game(name="Starting up... 🤖")
        await roxy.change_presence(status=discord.Status.online, activity=activity)
        update_roxy_status.start()
    if not award_voice_xp.is_running():
        award_voice_xp.start()

    print("✅ Roxy is fully operational!")

@roxy.event
async def on_member_join(member):
    """New member joins - Roxy welcomes them"""
    print(f"👋 New member joined: {member}")
    await roxy.db.add_user(member.id, str(member), member.display_name)
    
    # Roxy's welcome message - server Admins can change it with rr welcome
    import info_embeds  # Looked up each time so rr reload picks up changes
    settings = await roxy.db.get_guild_settings(member.guild.id)
    if not settings['welcome_enabled']:
        return
    channel = member.guild.get_channel(settings['welcome_channel_id'] or 0) or member.guild.system_channel
    if channel is None:
        return
    try:
        await channel.send(embed=info_embeds.welcome_embed(member, settings))
    except discord.HTTPException as e:
        print(f"❌ Couldn't send welcome message in {member.guild}: {e}")

@roxy.event
async def on_message(message):
    """Roxy tracks all messages"""
    if message.author.bot:
        return
    
    try:
        # Add user to Roxy's database
        await roxy.db.add_user(message.author.id, str(message.author), message.author.display_name)

        # Update message count and check for level up
        new_level = await roxy.db.update_message_count(message.author.id, xp_multiplier(roxy, message.author.id))

        # Roxy celebrates level ups!
        if new_level > 0:
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"Congratulations {message.author.mention}! You've reached **Level {new_level}**!",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed, delete_after=5)
        
    except Exception as e:
        print(f"❌ Error in on_message: {e}")
        import traceback
        traceback.print_exc()
    
    # Process commands
    await roxy.process_commands(message)

def get_current_activity(member):
    """Read a member's current game, non-game app and Spotify track from their presence"""
    game = None
    app = None
    track = None
    for activity in member.activities:
        if activity.type == discord.ActivityType.playing:
            # Non-game apps (VS Code, YouTube, ...) are tracked separately from gaming
            if activity.name.lower() in APP_ACTIVITIES:
                app = app or activity.name
            else:
                game = game or activity.name
        elif activity.type == discord.ActivityType.listening and track is None:
            # Spotify listening activity
            title = getattr(activity, 'title', None)
            artist = getattr(activity, 'artist', None)
            if title and artist:
                track = {'song': title, 'artist': artist, 'album': getattr(activity, 'album', None)}
    return game, track, app

async def sync_member_activity(member):
    """Bring Roxy's tracked sessions in line with a member's current presence.

    Compares against Roxy's own state instead of the event's 'before', so the duplicate
    presence events Discord sends (one per shared server) don't start or end sessions twice.
    In-memory state is updated before any await so concurrent duplicate events see it.
    """
    user_id = member.id
    game, track, app = get_current_activity(member)

    # ==================== GAMING ====================
    tracked_game = roxy.active_sessions.get(user_id)
    if game != tracked_game:
        if tracked_game:
            del roxy.active_sessions[user_id]
        if game:
            roxy.active_sessions[user_id] = game

        if tracked_game:
            await roxy.db.end_game_session(user_id, xp_multiplier(roxy, user_id))
        if game:
            await roxy.db.add_user(member.id, str(member), member.display_name)
            await roxy.db.start_game_session(user_id, game)

    # ==================== APPS (non-game) ====================
    tracked_app = roxy.active_apps.get(user_id)
    if app != tracked_app:
        if tracked_app:
            del roxy.active_apps[user_id]
        if app:
            roxy.active_apps[user_id] = app

        if tracked_app:
            await roxy.db.end_app_session(user_id, xp_multiplier(roxy, user_id))
        if app:
            await roxy.db.add_user(member.id, str(member), member.display_name)
            await roxy.db.start_app_session(user_id, app)

    # ==================== MUSIC LISTENING ====================
    tracked_track = roxy.active_listening.get(user_id)
    current_key = (track['song'], track['artist']) if track else None
    tracked_key = (tracked_track['song'], tracked_track['artist']) if tracked_track else None
    if current_key != tracked_key:
        if tracked_track:
            del roxy.active_listening[user_id]
        if track:
            roxy.active_listening[user_id] = track

        if tracked_track:
            await roxy.db.end_listening_session(user_id, xp_multiplier(roxy, user_id))
        if track:
            await roxy.db.add_user(member.id, str(member), member.display_name)
            await roxy.db.start_listening_session(user_id, track['song'], track['artist'], track['album'])

def counted_voice_channel(voice_state, guild):
    """The voice channel that counts as call time - None when not in voice or in the AFK channel"""
    channel = voice_state.channel if voice_state else None
    if channel is None or channel == guild.afk_channel:
        return None
    return channel

async def sync_member_voice(member, voice_state):
    """Start or end a voice session when someone joins, leaves or switches servers.
    Moving between channels in the same server continues the same session."""
    user_id = member.id
    channel = counted_voice_channel(voice_state, member.guild)
    tracked = roxy.active_voice.get(user_id)
    current = member.guild.id if channel else None

    # Leaving voice in one server doesn't end a call that's already running in another one
    if current is None and tracked is not None and tracked != member.guild.id:
        return
    if current == tracked:
        return

    if tracked is not None:
        del roxy.active_voice[user_id]
    if current is not None:
        roxy.active_voice[user_id] = current

    if tracked is not None:
        await roxy.db.end_voice_session(user_id, xp_multiplier(roxy, user_id))
    if current is not None:
        await roxy.db.add_user(member.id, str(member), member.display_name)
        await roxy.db.start_voice_session(user_id, member.guild.id, channel.name)

@roxy.event
async def on_voice_state_update(member, before, after):
    """Roxy tracks time in voice channels"""
    if member.bot:
        return
    try:
        await sync_member_voice(member, after)
    except Exception as e:
        print(f"❌ Error in on_voice_state_update: {e}")
        import traceback
        traceback.print_exc()

@roxy.event
async def on_presence_update(before, after):
    """Roxy tracks gaming activity and music listening"""
    if after.bot:
        return

    try:
        await sync_member_activity(after)
    except Exception as e:
        print(f"❌ Error in on_presence_update: {e}")
        import traceback
        traceback.print_exc()

def is_voice_active(voice_state) -> bool:
    """Counts for voice XP: not muted or deafened (by themselves or a moderator), not a silent stage listener"""
    return not (voice_state.self_mute or voice_state.mute or voice_state.self_deaf or voice_state.deaf or voice_state.suppress)

@tasks.loop(minutes=1)
async def award_voice_xp():
    """Every minute: voice XP for people actually talking with someone.
    No XP when alone, muted, deafened, or in the AFK channel - call time is still tracked."""
    credited = set()
    try:
        for guild in roxy.guilds:
            for channel in guild.voice_channels + guild.stage_channels:
                if channel == guild.afk_channel:
                    continue
                humans = [m for m in channel.members if not m.bot]
                if len(humans) < 2:
                    continue  # Alone (or only with bots) - no XP
                for member in humans:
                    if member.id in credited or member.id not in roxy.active_voice or not member.voice:
                        continue
                    if is_voice_active(member.voice):
                        credited.add(member.id)
                        await roxy.db.award_voice_minute(member.id, xp_multiplier(roxy, member.id))
    except Exception as e:
        print(f"❌ Error awarding voice XP: {e}")

@tasks.loop(minutes=3)
async def update_roxy_status():
    """Roxy updates her status regularly"""
    # An admin-set status (rr setstatus) stays until cleared
    if roxy.custom_status:
        return

    try:
        total_users = len(roxy.users)
        active_games = len(roxy.active_sessions)
        active_listeners = len(roxy.active_listening)
        
        # Roxy's personality-filled status messages
        status_messages = [
            f"👀 Watching {total_users} users",
            f"🎮 Tracking {active_games} gamers",
            f"🎵 Tracking {active_listeners} listeners",
            "📊 Crunching stats...",
            "💜 Use rr help",
            f"🏠 Active in {len(roxy.guilds)} servers",
            "🤖 Roxy at your service!",
            "📈 Analyzing activity patterns",
            "✨ Making stats magical",
            "🎶 Tracking your tunes!"
        ]
        
        message = random.choice(status_messages)
        activity = discord.Game(name=message)
        await roxy.change_presence(activity=activity)
        
    except Exception as e:
        print(f"❌ Error updating Roxy's status: {e}")

# ==================== REGULAR COMMANDS ====================

# Roxy's basic commands
@roxy.command(name='ping')
async def ping(ctx):
    """Check Roxy's response time"""
    latency = round(roxy.latency * 1000)
    
    # Roxy's personality in ping response
    if latency < 100:
        emoji = "⚡"
        comment = "Lightning fast!"
    elif latency < 200:
        emoji = "✅"
        comment = "Running smoothly!"
    else:
        emoji = "🐌"
        comment = "A bit slow, but I'm here!"
    
    embed = discord.Embed(
        title=f"{emoji} Roxy's Response Time",
        description=f"**{latency}ms** - {comment}",
        color=discord.Color.purple()
    )
    
    # Show admin indicator if user is admin
    if is_admin_id(ctx.author.id):
        embed.set_footer(text="👑 Owner")
    
    await ctx.send(embed=embed)

def link_buttons_view():
    """Link buttons (Patreon, Roxy server, ...) set in .env - None if none are set"""
    if not LINK_BUTTONS:
        return None
    view = discord.ui.View()
    for label, url in LINK_BUTTONS:
        view.add_item(discord.ui.Button(label=label, url=url))
    return view

@roxy.command(name='invite', aliases=['add'])
async def invite(ctx):
    """Link to add Roxy to another server"""
    invite_url = next((url for label, url in LINK_BUTTONS if label.startswith('➕')), None)
    if not invite_url:
        await ctx.send("❌ The invite link isn't set up yet.")
        return

    embed = discord.Embed(
        title="➕ Add Roxy to your server",
        description="Levels, gaming time and Spotify stats for your members - all automatic, no sign-ups.\n\nClick the button below, pick your server and press **Authorize**. You need **Manage Server** permission in that server.",
        color=discord.Color.purple()
    )
    if roxy.user:
        embed.set_thumbnail(url=roxy.user.display_avatar.url)
    await ctx.send(embed=embed, view=link_buttons_view())

@roxy.command(name='help')
async def help_command(ctx, *, command=None):
    """Roxy's help menu"""
    if command and command.lower() == 'games':
        # Show games-specific help
        embed = discord.Embed(
            title="🎮 Gaming Commands Help",
            description="Complete guide to Roxy's gaming features!",
            color=0x9b59b6
        )
        
        embed.add_field(
            name="📊 **Main Gaming Command**",
            value="`rr games [@user]` - Show gaming overview, top 3 favorites, latest 5 sessions, achievements",
            inline=False
        )
        
        embed.add_field(
            name="🎮 **Games Sub-Commands**",
            value="`rr games list [@user]` - Show all favorite games ranked by playtime\n`rr games history [@user]` - Show complete gaming history chronologically",
            inline=False
        )
        
        embed.add_field(
            name="🔧 **What's Tracked**",
            value="• Gaming sessions (when you start/stop playing)\n• Total playtime per game\n• Session duration and frequency\n• Gaming achievements and milestones\n• XP earned from gaming (1 XP per minute)",
            inline=False
        )
        
        embed.add_field(
            name="🏆 **Achievement Categories**",
            value="• **Playtime Milestones** - 1h, 5h, 10h, 20h, 50h, 100h+\n• **Session Achievements** - 5, 10, 20, 50, 100+ sessions\n• **Marathon Sessions** - 1h, 2h, 3h, 5h, 6h+ single sessions\n• **Game Devotion** - Dedication to specific games\n• **Game Variety** - Playing multiple different games",
            inline=False
        )
        
        embed.add_field(
            name="💡 **Tips**",
            value="• Your Discord status must show 'Playing [Game]' to be tracked\n• Sessions are automatically detected when you start/stop games\n• All historical data is preserved and analyzed\n• Use `rr refresh` if playtime seems stuck",
            inline=False
        )
        
        embed.set_footer(text="💜 Use rr help for all commands • Roxy tracks your gaming automatically!")
        
        await ctx.send(embed=embed, view=link_buttons_view())
        return
    
    elif command and command.lower() == 'music':
        # Show music-specific help
        embed = discord.Embed(
            title="🎵 Music Commands Help",
            description="Complete guide to Roxy's music listening features!",
            color=0x1db954  # Spotify green
        )
        
        embed.add_field(
            name="📊 **Main Music Command**",
            value="`rr music [@user]` - Show listening overview, top 3 artists, latest 5 tracks, achievements",
            inline=False
        )
        
        embed.add_field(
            name="🎵 **Music Sub-Commands**",
            value="`rr music artists [@user]` - Show all favorite artists ranked by listening time\n`rr music history [@user]` - Show complete listening history chronologically\n`rr music songs [@user]` - Show favorite songs ranked by listening time",
            inline=False
        )
        
        embed.add_field(
            name="🔧 **What's Tracked**",
            value="• Spotify listening sessions (automatic detection)\n• Total listening time per artist/song\n• Session duration and frequency\n• Music achievements and milestones\n• XP earned from listening (1 XP per 2 minutes)",
            inline=False
        )
        
        embed.add_field(
            name="🏆 **Achievement Categories**",
            value="• **Listening Time Milestones** - 1h, 5h, 10h, 50h, 100h, 500h+\n• **Session Achievements** - 10, 50, 100, 500, 1000+ sessions\n• **Marathon Listening** - 1h, 2h, 3h, 6h, 8h+ single sessions\n• **Artist Devotion** - Dedication to specific artists\n• **Music Variety** - Listening to many different artists",
            inline=False
        )
        
        embed.add_field(
            name="💡 **Tips**",
            value="• Must be listening to Spotify for tracking to work\n• Sessions are automatically detected when you start/stop listening\n• All historical data is preserved and analyzed\n• Use `rr refresh` if listening time seems stuck",
            inline=False
        )
        
        embed.set_footer(text="💜 Use rr help for all commands • Roxy tracks your Spotify automatically!")
        
        await ctx.send(embed=embed, view=link_buttons_view())
        return
    
    # Regular help menu
    embed = discord.Embed(
        title="💜 Roxy's Command Center",
        description="Here's everything I can do for you!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="📊 Profile Commands",
        value="`rr profile / p [@user]` or `/profile` - View profile\n`rr level [@user]` - Check level & XP\n`rr games [@user]` - Gaming analytics & achievements\n`rr music [@user]` - Music listening analytics\n`rr apps [@user]` - Time in apps (VS Code, YouTube...)",
        inline=False
    )
    
    embed.add_field(
        name="🏆 Leaderboards",
        value="`rr top messages` - Message leaderboard\n`rr top voice` - Voice call leaderboard\n`rr top playtime` - Gaming leaderboard\n`rr top apps` - App time leaderboard\n`rr top listening` - Music listening leaderboard\n`rr top level` - Level rankings",
        inline=False
    )
    
    embed.add_field(
        name="🎮🎵 Activity Commands",
        value="`rr help games` - Gaming commands help\n`rr help music` - Music commands help",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Info Commands",
        value="`rr serverinfo` - This server's Discord info\n`rr userinfo [@user]` or `/userinfo` - Discord profile (Server / Global)",
        inline=False
    )

    embed.add_field(
        name="🤖 Bot Commands",
        value="`rr ping` - Check my response time\n`rr info` - Learn about me\n`rr invite` - Add me to your server\n`rr help` - This menu",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Debug Commands",
        value="`rr debug` - Check your stats\n`rr sessions` - View active sessions\n`rr refresh` - Fix your stuck stats",
        inline=False
    )
    
    embed.set_footer(text="💡 Prefix: rr (e.g. rr help)")
    user_detailed = embed

    user_compact = discord.Embed(title="💜 Roxy's Command Center", description="Compact view - switch to **Detailed** for explanations.", color=discord.Color.purple())
    user_compact.add_field(name="📊 Profile", value="`rr p` `rr level` `rr games` `rr music` `rr apps` `/profile`", inline=False)
    user_compact.add_field(name="🏆 Leaderboards", value="`rr top` + `messages` `voice` `playtime` `apps` `listening` `level`", inline=False)
    user_compact.add_field(name="ℹ️ Info", value="`rr serverinfo` `rr userinfo` `/userinfo` `rr info` `rr ping` `rr invite`", inline=False)
    user_compact.add_field(name="🔧 Other", value="`rr help games` `rr help music` `rr sessions` `rr debug` `rr refresh`", inline=False)
    user_compact.set_footer(text="💡 Prefix: rr (e.g. rr help)")

    # Help pages by role: everyone gets User, server Admins also Admin, Roxy's owner also Owner
    is_owner = is_admin_id(ctx.author.id)
    is_admin_here = is_owner or (ctx.guild is not None and is_server_admin(ctx.author))

    admin_detailed = discord.Embed(
        title="🛡️ Server Admin Commands",
        description="For members with **Administrator** permission and the server owner. These only affect **this server**.",
        color=discord.Color.blue()
    )
    admin_detailed.add_field(name="📊 Server", value="`rr serverstats` - Overview, member list and Roxy stats for this server", inline=False)
    admin_detailed.add_field(name="📢 Announcements", value="`rr announce [#channel] <message>` - Post an announcement in this server", inline=False)
    admin_detailed.add_field(name="👋 Welcome Message", value="`rr welcome` - See and change the welcome message for new members (text, title, channel, on/off, preview)", inline=False)
    admin_detailed.set_footer(text="👑 Owner view" if is_owner else "🛡️ You are an Admin of this server")

    admin_compact = discord.Embed(title="🛡️ Server Admin Commands", description="`rr serverstats` `rr announce` `rr welcome`", color=discord.Color.blue())
    admin_compact.set_footer(text="👑 Owner view" if is_owner else "🛡️ You are an Admin of this server")

    pages = {
        'user': ('User', '💜', 'Commands for everyone', user_detailed, user_compact),
        'admin': ('Admin', '🛡️', 'Server Admin commands', admin_detailed, admin_compact),
    }

    if is_owner:
        owner_detailed = discord.Embed(title="👑 Roxy Owner Control Panel", description="**Owner-only commands** for managing Roxy Bot", color=discord.Color.gold())
        owner_detailed.add_field(
            name="👥 User Management",
            value="`rr addxp <@user> <amount>` - Give XP to user\n`rr setlevel <@user> <level>` - Set user level\n`rr resetuser <@user>` - Reset user stats\n`rr deleteuser <@user or ID>` - Erase all their data (deletion requests)\n`rr viewuser <@user>` - View detailed user data\n`rr forceupdate <@user>` - Recalculate a user's totals",
            inline=False
        )
        owner_detailed.add_field(
            name="🏆 Achievement Management",
            value="`rr ach` - Achievement control panel\n`rr ach users <achievement>` - Who has an achievement\n`rr giveach <@user> <achievement>` - Grant achievement\n`rr removeach <@user> <achievement>` - Remove achievement",
            inline=False
        )
        owner_detailed.add_field(
            name="🗄️ Database Management",
            value="`/dbstats` - Database statistics & Excel export (only you)\n`rr cleanup` - Clean inactive users\n`rr backup` - Create database backup\n`rr totalstats` - Global statistics\n`rr serverstats [server id]` - Any server's info & members",
            inline=False
        )
        owner_detailed.add_field(
            name="🤖 Bot Control",
            value="`rr setstatus <message>` - Set bot status (`clear` to resume rotation)\n`rr announce [#channel] <message>` - Announcement in any server\n`rr reload` - Reload Roxy's code\n`rr shutdown` - Save sessions and shut down",
            inline=False
        )
        owner_detailed.add_field(
            name="🔧 Debug & Maintenance",
            value="`rr clearsessions` - End all active sessions\n`rr presence [@user]` - What Discord shares with Roxy\n`/logs [limit]` - Recent logs (only you can see them)\n`rr testxp` - Test XP system",
            inline=False
        )
        owner_detailed.set_footer(text="👑 You are Roxy's Owner | Owner commands are ignored for everyone else")

        owner_compact = discord.Embed(title="👑 Owner Commands", description="Compact view - switch to **Detailed** for explanations.", color=discord.Color.gold())
        owner_compact.add_field(name="👥 Users", value="`rr addxp` `rr setlevel` `rr resetuser` `rr deleteuser` `rr viewuser` `rr forceupdate`", inline=False)
        owner_compact.add_field(name="🏆 Achievements", value="`rr ach` `rr ach users` `rr giveach` `rr removeach`", inline=False)
        owner_compact.add_field(name="🗄️ Data & Stats", value="`/dbstats` `/logs` `rr totalstats` `rr serverstats <id>` `rr cleanup` `rr backup`", inline=False)
        owner_compact.add_field(name="🤖 Bot Control", value="`rr setstatus` `rr announce` `rr reload` `rr shutdown` `rr clearsessions` `rr presence` `rr testxp`", inline=False)
        owner_compact.set_footer(text="👑 You are Roxy's Owner")
        pages['owner'] = ('Owner', '👑', 'Owner-only commands', owner_detailed, owner_compact)

    state = {'page': 'user', 'compact': False}

    def current_embed():
        _, _, _, detailed, compact = pages[state['page']]
        return compact if state['compact'] else detailed

    class HelpSelect(discord.ui.Select):
        def __init__(self):
            options = [discord.SelectOption(label=label, emoji=emoji, description=desc, value=key, default=(key == state['page']))
                       for key, (label, emoji, desc, _, _) in pages.items()]
            super().__init__(placeholder="📚 Choose a help page...", options=options, row=0)

        async def callback(self, interaction):
            state['page'] = self.values[0]
            await interaction.response.edit_message(embed=current_embed(), view=HelpView())

    class ModeSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label='Detailed', emoji='📖', description='Every command with an explanation', value='detailed', default=not state['compact']),
                discord.SelectOption(label='Compact', emoji='📋', description='Just the commands, grouped', value='compact', default=state['compact']),
            ]
            super().__init__(placeholder="📖 Choose a view mode...", options=options, row=1)

        async def callback(self, interaction):
            state['compact'] = self.values[0] == 'compact'
            await interaction.response.edit_message(embed=current_embed(), view=HelpView())

    class HelpView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            # The page dropdown only for server Admins and the owner
            if is_admin_here:
                self.add_item(HelpSelect())
            self.add_item(ModeSelect())
            for label, url in LINK_BUTTONS:
                self.add_item(discord.ui.Button(label=label, url=url, row=2))

        async def interaction_check(self, interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ This menu isn't yours - use `rr help` to get your own.", ephemeral=True)
                return False
            return True

    await ctx.send(embed=current_embed(), view=HelpView())

# Debug commands (Available to everyone)
@roxy.command(name='debug')
async def debug_user(ctx, member: discord.Member = None):
    """Debug user stats"""
    if member is None:
        member = ctx.author
    
    try:
        stats = await roxy.db.get_user_stats(member.id)
        if stats:
            embed = discord.Embed(
                title=f"🔧 Debug Info for {member.display_name}",
                color=discord.Color.orange()
            )
            
            # Format playtime for readability
            total_playtime = stats[5] if len(stats) > 5 else 0
            hours = total_playtime // 3600
            minutes = (total_playtime % 3600) // 60
            
            # Format listening time for readability
            total_listening_time = stats[10] if len(stats) > 10 else 0
            listening_hours = total_listening_time // 3600
            listening_minutes = (total_listening_time % 3600) // 60
            
            embed.add_field(
                name="📊 Current Stats",
                value=f"**Messages:** {stats[4] if len(stats) > 4 else 0}\n**Playtime:** {hours}h {minutes}m ({total_playtime}s total)\n**Listening Time:** {listening_hours}h {listening_minutes}m ({total_listening_time}s total)\n**Level:** {stats[8] if len(stats) > 8 else 1}\n**XP:** {stats[9] if len(stats) > 9 else 0}",
                inline=False
            )
            
            current_game = stats[6] if len(stats) > 6 else None
            current_song = stats[11] if len(stats) > 11 else None
            current_artist = stats[12] if len(stats) > 12 else None
            
            embed.add_field(
                name="🎮🎵 Activity Info",
                value=f"**Current Game:** {current_game or 'None'}\n**Current Song:** {current_song or 'None'}\n**Current Artist:** {current_artist or 'None'}\n**In Active Gaming:** {'Yes' if member.id in roxy.active_sessions else 'No'}\n**In Active Listening:** {'Yes' if member.id in roxy.active_listening else 'No'}",
                inline=False
            )
            
            # Show raw data only to admin
            if is_admin_id(ctx.author.id):
                embed.add_field(
                    name="Raw Database Data",
                    value=f"```\nUser ID: {stats[0]}\nUsername: {stats[1] if len(stats) > 1 else 'N/A'}\nDisplay Name: {stats[2] if len(stats) > 2 else 'N/A'}\nJoin Date: {stats[3] if len(stats) > 3 else 'N/A'}\nLast Seen: {stats[7] if len(stats) > 7 else 'N/A'}\nStats Length: {len(stats)}\n```",
                    inline=False
                )
        else:
            embed = discord.Embed(
                title="❌ No data found",
                description="User not in database",
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Debug error: {e}")

@roxy.command(name='testxp')
@is_admin()
async def test_xp(ctx):
    """Test XP system (Owner only)"""
    try:
        # Add user and update message count
        await roxy.db.add_user(ctx.author.id, str(ctx.author), ctx.author.display_name)
        new_level = await roxy.db.update_message_count(ctx.author.id)
        
        # Get updated stats
        stats = await roxy.db.get_user_stats(ctx.author.id)
        
        embed = discord.Embed(
            title="🧪 XP Test Results",
            color=discord.Color.green()
        )
        
        if stats:
            total_playtime = stats[5] if len(stats) > 5 else 0
            total_listening_time = stats[10] if len(stats) > 10 else 0
            hours = total_playtime // 3600
            minutes = (total_playtime % 3600) // 60
            listening_hours = total_listening_time // 3600
            listening_minutes = (total_listening_time % 3600) // 60
            
            embed.add_field(
                name="Current Stats",
                value=f"Messages: {stats[4] if len(stats) > 4 else 0}\nPlaytime: {hours}h {minutes}m\nListening: {listening_hours}h {listening_minutes}m\nXP: {stats[9] if len(stats) > 9 else 0}\nLevel: {stats[8] if len(stats) > 8 else 1}",
                inline=False
            )
            
            if new_level > 0:
                embed.add_field(
                    name="Level Up!",
                    value=f"You leveled up to {new_level}!",
                    inline=False
                )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

@roxy.command(name='refresh')
async def refresh_stats(ctx, member: discord.Member = None):
    """Refresh user stats (fix stuck playtime/listening time)"""
    if member is None:
        member = ctx.author

    # Only the admin can refresh someone else's stats
    if member.id != ctx.author.id and not is_admin_id(ctx.author.id):
        await ctx.send("❌ You can only refresh your own stats. Use `rr refresh` without mentioning anyone.")
        return

    try:
        # Refresh the user's stats
        total_playtime, total_listening_time = await roxy.db.force_refresh_user_stats(member.id)
        
        play_hours = total_playtime // 3600
        play_minutes = (total_playtime % 3600) // 60
        listen_hours = total_listening_time // 3600
        listen_minutes = (total_listening_time % 3600) // 60
        
        embed = discord.Embed(
            title="🔄 Stats Refreshed",
            description=f"Recalculated stats for {member.display_name}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Updated Stats",
            value=f"**Gaming:** {play_hours}h {play_minutes}m ({total_playtime}s total)\n**Listening:** {listen_hours}h {listen_minutes}m ({total_listening_time}s total)",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Refresh error: {e}")

# ==================== EARLY ADOPTER ====================

EARLY_ADOPTER = "Early Adopter"
EARLY_ADOPTER_DEADLINE = datetime(2027, 1, 1, tzinfo=timezone.utc)  # Anyone using Roxy before 2027 (UTC)
early_adopters_checked = set()  # Users already checked this run - saves a database call per command

@roxy.event
async def on_command(ctx):
    """Grant Early Adopter to anyone who uses a Roxy command before 2027 (UTC)"""
    user = ctx.author
    if user.bot or user.id in early_adopters_checked:
        return
    if datetime.now(timezone.utc) >= EARLY_ADOPTER_DEADLINE:
        return
    early_adopters_checked.add(user.id)

    try:
        await roxy.db.add_user(user.id, str(user), user.display_name)
        if await roxy.db.give_achievement(user.id, EARLY_ADOPTER):
            embed = discord.Embed(
                title="🏅 Achievement Unlocked: Early Adopter!",
                description=f"Thanks for using Roxy early, {user.mention}! This badge is only available until the end of 2026 (UTC).",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed, delete_after=15)
    except Exception as e:
        early_adopters_checked.discard(user.id)  # Try again next command
        print(f"❌ Error granting Early Adopter: {e}")

# Error handler - Silent for admin commands
@roxy.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.HybridCommandError):
        error = error.original  # Errors from the slash-command side of hybrid commands

    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ This command only works in a server.", ephemeral=True)
    elif ctx.interaction is not None and isinstance(error, (commands.CheckFailure, app_commands.CheckFailure)):
        # A slash command must always get a reply, or Discord shows "The application did not respond"
        if not ctx.interaction.response.is_done():
            await ctx.interaction.response.send_message("❌ This command is only for Roxy's owner or server admins.", ephemeral=True)
    elif isinstance(error, commands.CheckFailure):
        # Completely ignore failed admin commands - no response
        pass
    elif isinstance(error, commands.CommandNotFound):
        # Ignore command not found errors
        pass
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing `{error.param.name}`. Usage: `rr {ctx.command.qualified_name} {ctx.command.signature}`")
    elif isinstance(error, (commands.MemberNotFound, commands.ChannelNotFound)):
        await ctx.send(f"❌ {error}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid value. Usage: `rr {ctx.command.qualified_name} {ctx.command.signature}`")
    else:
        # Only log unexpected errors
        print(f"❌ Command error: {error}")

def acquire_single_instance_lock():
    """Only one Roxy per PC - two copies with the same token answer every command twice.
    Holding a local port works as the lock: a second copy can't bind it."""
    import socket
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        lock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        lock.bind(('127.0.0.1', 47653))
    except OSError:
        return None
    return lock

# Run Roxy!
# Exit codes (used by start_roxy.bat): 0 = clean shutdown, 1 = crash (restart), 2 = no token, 3 = already running
if __name__ == "__main__":
    import sys
    
    instance_lock = acquire_single_instance_lock()
    if instance_lock is None:
        print("⚠️ Roxy is already running on this PC - not starting a second copy.")
        sys.exit(3)
    
    token = os.getenv('DISCORD_TOKEN')
    if token is None:
        print("❌ DISCORD_TOKEN not found in environment variables!")
        print("🔧 Check your .env file and make sure DISCORD_TOKEN is set correctly!")
        sys.exit(2)
    
    try:
        roxy.run(token)
    except discord.LoginFailure as e:
        print(f"❌ Discord rejected the token: {e}")
        print("🔧 Check your .env file and make sure DISCORD_TOKEN is set correctly!")
        sys.exit(2)
    except Exception as e:
        print(f"❌ Roxy crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
