import discord
from discord.ext import commands, tasks
import os
import asyncio
import random
import aiosqlite
import time
import psutil
from datetime import datetime
from dotenv import load_dotenv
from database import RoxyDatabase

# Load Roxy's configuration
load_dotenv()

# Roxy's personality and intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

class RoxyBot(commands.Bot):
    """Roxy - Your friendly Discord stats bot"""
    
    def __init__(self):
        super().__init__(
            command_prefix=['!r ', '!'],
            intents=intents,
            help_command=None
        )
        self.db = RoxyDatabase()
        self.active_sessions = {}  # Gaming sessions
        self.active_listening = {}  # Music listening sessions
        self.start_time: float = 0.0  # Add start_time attribute with type hint
        
    async def setup_hook(self):
        """Roxy's startup setup"""
        await self.db.init_db()
        await self.load_extension('cogs.stats')
        await self.load_extension('cogs.admin')  # Load admin cog
        print("🤖 Roxy's cogs loaded successfully!")

# Initialize Roxy
roxy = RoxyBot()

# Store bot start time for uptime calculation
@roxy.event
async def on_ready():
    """Roxy comes online!"""
    roxy.start_time = time.time()  # Add this line for uptime tracking
    
    print(f'🌟 {roxy.user} is now online and ready!')
    print(f'📊 Roxy is active in {len(roxy.guilds)} servers')
    print(f'👥 Watching over {len(roxy.users)} users')
    
    # Find admin user (if needed for display purposes)
    ADMIN_USER_ID = 526795891487670302  # Your Discord User ID
    admin_user = roxy.get_user(ADMIN_USER_ID)
    if admin_user:
        print(f'👑 Admin: {admin_user} ({ADMIN_USER_ID})')
    else:
        print(f'⚠️ Admin user {ADMIN_USER_ID} not found')
    
    # Roxy's startup status
    activity = discord.Game(name="Starting up... 🤖")
    await roxy.change_presence(status=discord.Status.online, activity=activity)
    
    # Start Roxy's background tasks
    update_roxy_status.start()
    
    print("✅ Roxy is fully operational!")

@roxy.event
async def on_member_join(member):
    """New member joins - Roxy welcomes them"""
    print(f"👋 New member joined: {member}")
    await roxy.db.add_user(member.id, str(member), member.display_name)
    
    # Roxy's welcome message (optional)
    if member.guild.system_channel:
        embed = discord.Embed(
            title="🎉 Welcome to the server!",
            description=f"Hey {member.mention}! I'm **Roxy**, your friendly stats bot. Use `!r help` to see what I can do!",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await member.guild.system_channel.send(embed=embed)

@roxy.event
async def on_message(message):
    """Roxy tracks all messages"""
    if message.author.bot:
        return
    
    try:
        print(f"💬 Message from {message.author.display_name}: {message.content[:50]}...")
        
        # Add user to Roxy's database
        await roxy.db.add_user(message.author.id, str(message.author), message.author.display_name)
        print(f"✅ User added/updated: {message.author.display_name}")
        
        # Update message count and check for level up
        new_level = await roxy.db.update_message_count(message.author.id)
        print(f"📊 Message count updated for {message.author.display_name}, new level: {new_level}")
        
        # Roxy celebrates level ups!
        if new_level > 0:
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"Congratulations {message.author.mention}! You've reached **Level {new_level}**!",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed, delete_after=5)
            print(f"🎉 Level up celebration sent for {message.author.display_name}!")
        
    except Exception as e:
        print(f"❌ Error in on_message: {e}")
        import traceback
        traceback.print_exc()
    
    # Process commands
    await roxy.process_commands(message)

@roxy.event
async def on_presence_update(before, after):
    """Roxy tracks gaming activity and music listening"""
    if before.bot or after.bot:
        return
    
    # Skip if it's Roxy herself to avoid self-tracking
    if roxy.user and after.id == roxy.user.id:
        return
    
    try:
        user_id = after.id
        
        # Check for game status changes
        before_game = None
        after_game = None
        
        # Check for music listening changes
        before_song = None
        before_artist = None
        after_song = None
        after_artist = None
        after_album = None
        
        if before.activities:
            for activity in before.activities:
                if activity.type == discord.ActivityType.playing:
                    before_game = activity.name
                elif activity.type == discord.ActivityType.listening:
                    # Spotify listening activity
                    if hasattr(activity, 'title') and hasattr(activity, 'artist'):
                        before_song = activity.title
                        before_artist = activity.artist
        
        if after.activities:
            for activity in after.activities:
                if activity.type == discord.ActivityType.playing:
                    after_game = activity.name
                elif activity.type == discord.ActivityType.listening:
                    # Spotify listening activity
                    if hasattr(activity, 'title') and hasattr(activity, 'artist'):
                        after_song = activity.title
                        after_artist = activity.artist
                        after_album = getattr(activity, 'album', None)
        
        # ==================== HANDLE GAMING CHANGES ====================
        if before_game != after_game:
            # End previous gaming session
            if before_game:
                try:
                    duration = await roxy.db.end_game_session(user_id)
                    
                    # Only remove from active_sessions if user is actually in it
                    if user_id in roxy.active_sessions:
                        del roxy.active_sessions[user_id]
                    
                    minutes = duration // 60
                    seconds = duration % 60
                    print(f"🎮 {after.display_name} finished playing {before_game} ({minutes}m {seconds}s)")
                    
                except Exception as e:
                    print(f"❌ Error ending game session: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start new gaming session
            if after_game:
                try:
                    await roxy.db.start_game_session(user_id, after_game)
                    roxy.active_sessions[user_id] = after_game
                    print(f"🎮 {after.display_name} started playing {after_game}")
                except Exception as e:
                    print(f"❌ Error starting game session: {e}")
                    import traceback
                    traceback.print_exc()
        
        # ==================== HANDLE MUSIC LISTENING CHANGES ====================
        # Check if listening status changed
        before_listening = f"{before_song} by {before_artist}" if before_song and before_artist else None
        after_listening = f"{after_song} by {after_artist}" if after_song and after_artist else None
        
        if before_listening != after_listening:
            # End previous listening session
            if before_listening:
                try:
                    duration = await roxy.db.end_listening_session(user_id)
                    
                    # Only remove from active_listening if user is actually in it
                    if user_id in roxy.active_listening:
                        del roxy.active_listening[user_id]
                    
                    minutes = duration // 60
                    seconds = duration % 60
                    print(f"🎵 {after.display_name} finished listening to {before_listening} ({minutes}m {seconds}s)")
                    
                except Exception as e:
                    print(f"❌ Error ending listening session: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start new listening session
            if after_listening and after_song and after_artist:
                try:
                    await roxy.db.start_listening_session(user_id, after_song, after_artist, after_album)
                    roxy.active_listening[user_id] = {
                        'song': after_song,
                        'artist': after_artist,
                        'album': after_album
                    }
                    print(f"🎵 {after.display_name} started listening to {after_listening}")
                except Exception as e:
                    print(f"❌ Error starting listening session: {e}")
                    import traceback
                    traceback.print_exc()
                    
    except Exception as e:
        print(f"❌ Error in on_presence_update: {e}")
        import traceback
        traceback.print_exc()

@tasks.loop(minutes=3)
async def update_roxy_status():
    """Roxy updates her status regularly"""
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
            "💜 Use !r help",
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
    ADMIN_USER_ID = 526795891487670302  # Your Discord User ID
    if ctx.author.id == ADMIN_USER_ID:
        embed.set_footer(text="👑 Administrator")
    
    await ctx.send(embed=embed)

@roxy.command(name='info', aliases=['about'])
async def bot_info(ctx):
    """Learn about Roxy"""
    embed = discord.Embed(
        title="🤖 About Roxy Bot",
        description="Hi! I'm **Roxy**, your friendly neighborhood stats bot! I love tracking gaming sessions, music listening, messages, and helping you level up!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="📊 What I Do",
        value="• Track your gaming sessions\n• Monitor music listening (Spotify)\n• Monitor message counts\n• XP and leveling system\n• Server leaderboards\n• User profiles & statistics",
        inline=False
    )
    
    embed.add_field(name="🏠 Servers", value=len(roxy.guilds), inline=True)
    embed.add_field(name="👥 Users", value=len(roxy.users), inline=True)
    embed.add_field(name="🎮 Active Gamers", value=len(roxy.active_sessions), inline=True)
    embed.add_field(name="🎵 Active Listeners", value=len(roxy.active_listening), inline=True)
    
    # Show admin info only if user is admin
    ADMIN_USER_ID = 526795891487670302  # Your Discord User ID
    if ctx.author.id == ADMIN_USER_ID:
        embed.add_field(
            name="👑 Admin Commands",
            value="Use `!r admin` for admin controls",
            inline=False
        )
        embed.set_footer(text="Made with ❤️ using discord.py | You are Roxy's Administrator")
    else:
        embed.set_footer(text="Made with ❤️ using discord.py | Use !r help for commands")
    
    if roxy.user:
        embed.set_thumbnail(url=roxy.user.avatar.url if roxy.user.avatar else roxy.user.default_avatar.url)
    
    await ctx.send(embed=embed)

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
            value="`!r games [@user]` - Show gaming overview, top 3 favorites, latest 5 sessions, achievements",
            inline=False
        )
        
        embed.add_field(
            name="🎮 **Games Sub-Commands**",
            value="`!r games list [@user]` - Show all favorite games ranked by playtime\n`!r games history [@user]` - Show complete gaming history chronologically",
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
            value="• Your Discord status must show 'Playing [Game]' to be tracked\n• Sessions are automatically detected when you start/stop games\n• All historical data is preserved and analyzed\n• Use `!r refresh` if playtime seems stuck",
            inline=False
        )
        
        embed.set_footer(text="💜 Use !r help for all commands • Roxy tracks your gaming automatically!")
        
        await ctx.send(embed=embed)
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
            value="`!r music [@user]` - Show listening overview, top 3 artists, latest 5 tracks, achievements",
            inline=False
        )
        
        embed.add_field(
            name="🎵 **Music Sub-Commands**",
            value="`!r music artists [@user]` - Show all favorite artists ranked by listening time\n`!r music history [@user]` - Show complete listening history chronologically\n`!r music songs [@user]` - Show favorite songs ranked by listening time",
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
            value="• Must be listening to Spotify for tracking to work\n• Sessions are automatically detected when you start/stop listening\n• All historical data is preserved and analyzed\n• Use `!r refresh` if listening time seems stuck",
            inline=False
        )
        
        embed.set_footer(text="💜 Use !r help for all commands • Roxy tracks your Spotify automatically!")
        
        await ctx.send(embed=embed)
        return
    
    # Regular help menu
    embed = discord.Embed(
        title="💜 Roxy's Command Center",
        description="Here's everything I can do for you!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="📊 Profile Commands",
        value="`!r profile / p [@user]` - View profile\n`!r level [@user]` - Check level & XP\n`!r games [@user]` - Gaming analytics & achievements\n`!r music [@user]` - Music listening analytics",
        inline=False
    )
    
    embed.add_field(
        name="🏆 Leaderboards",
        value="`!r top messages` - Message leaderboard\n`!r top playtime` - Gaming leaderboard\n`!r top listening` - Music listening leaderboard\n`!r top level` - Level rankings",
        inline=False
    )
    
    embed.add_field(
        name="🎮🎵 Activity Commands",
        value="`!r help games` - Gaming commands help\n`!r help music` - Music commands help",
        inline=False
    )
    
    embed.add_field(
        name="🤖 Bot Commands",
        value="`!r ping` - Check my response time\n`!r info` - Learn about me\n`!r help` - This menu",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Debug Commands",
        value="`!r debug` - Check your stats\n`!r testxp` - Test XP system\n`!r sessions` - View active sessions\n`!r refresh` - Fix stuck stats",
        inline=False
    )
    
    # Show admin section only if user is admin
    ADMIN_USER_ID = 526795891487670302  # Your Discord User ID
    if ctx.author.id == ADMIN_USER_ID:
        embed.add_field(
            name="👑 Admin Commands",
            value="`!r admin` - Admin control panel\n*(Admin-only commands)*",
            inline=False
        )
        embed.set_footer(text="💡 Tip: You can use ! as a shortcut | 👑 You are Administrator")
    else:
        embed.set_footer(text="💡 Tip: You can use ! as a shortcut for !r")
    
    await ctx.send(embed=embed)

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
            ADMIN_USER_ID = 526795891487670302  # Your Discord User ID
            if ctx.author.id == ADMIN_USER_ID:
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

@roxy.command(name='sessions')
async def active_sessions(ctx):
    """View active gaming and listening sessions"""
    embed = discord.Embed(
        title="🎮🎵 Active Sessions",
        description="Currently active gaming and listening sessions:",
        color=discord.Color.blue()
    )
    
    # Gaming sessions
    if roxy.active_sessions:
        session_list = ""
        for user_id, game in roxy.active_sessions.items():
            member = ctx.guild.get_member(user_id)
            if member:
                session_list += f"• **{member.display_name}** playing *{game}*\n"
        
        embed.add_field(
            name="🎮 Gaming Sessions",
            value=session_list or "None found in this server",
            inline=False
        )
    else:
        embed.add_field(
            name="🎮 Gaming Sessions",
            value="No one is currently gaming!",
            inline=False
        )
    
    # Music listening sessions
    if roxy.active_listening:
        listening_list = ""
        for user_id, music_info in roxy.active_listening.items():
            member = ctx.guild.get_member(user_id)
            if member:
                song = music_info.get('song', 'Unknown')
                artist = music_info.get('artist', 'Unknown')
                listening_list += f"• **{member.display_name}** listening to *{song}* by *{artist}*\n"
        
        embed.add_field(
            name="🎵 Listening Sessions",
            value=listening_list or "None found in this server",
            inline=False
        )
    else:
        embed.add_field(
            name="🎵 Listening Sessions",
            value="No one is currently listening to music!",
            inline=False
        )
    
    await ctx.send(embed=embed)

@roxy.command(name='testxp')
async def test_xp(ctx):
    """Test XP system"""
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

# Error handler - Silent for admin commands
@roxy.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        # Completely ignore failed admin commands - no response
        pass
    elif isinstance(error, commands.CommandNotFound):
        # Ignore command not found errors
        pass
    else:
        # Only log unexpected errors
        print(f"❌ Command error: {error}")

# Run Roxy!
if __name__ == "__main__":
    try:
        token = os.getenv('DISCORD_TOKEN')
        if token is None:
            print("❌ DISCORD_TOKEN not found in environment variables!")
            print("🔧 Check your .env file and make sure DISCORD_TOKEN is set correctly!")
        else:
            roxy.run(token)
    except Exception as e:
        print(f"❌ Failed to start Roxy: {e}")
        print("🔧 Check your .env file and make sure DISCORD_TOKEN is set correctly!")