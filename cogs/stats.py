import discord
from discord.ext import commands
from discord import app_commands
from database import (RoxyDatabase, format_duration, MESSAGE_XP, VOICE_XP_PER_MINUTE, GAMING_XP_PER_MINUTE,
                      APP_XP_PER_MINUTE, LISTENING_XP_PER_2_MINUTES)
from config import is_admin_id, is_server_admin, LINK_BUTTONS
from info_embeds import server_overview_embed, profile_embed, global_profile_embed
from patreon import get_patron_tier, get_patrons
from datetime import datetime, timedelta
import asyncio
import re

class RoxyStats(commands.Cog):
    """Roxy's statistics and analytics system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = RoxyDatabase()
    
    @commands.hybrid_command(name='profile', aliases=['p', 'stats'], description="Roxy profile: level, XP, gaming and music stats")
    @app_commands.describe(member="Whose profile to show (default: you)")
    async def user_profile(self, ctx, member: discord.Member = None):
        """Display comprehensive user profile with navigation"""
        await ctx.defer()  # Slash commands must answer within 3 seconds - this buys time
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "profile")
    
    @commands.command(name='level', aliases=['lvl', 'xp'])
    async def user_level(self, ctx, member: discord.Member = None):
        """Quick level and XP check with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "level")
    
    @commands.group(name='games', aliases=['gaming', 'activity'], invoke_without_command=True)
    async def user_games(self, ctx, member: discord.Member = None):
        """Show user's gaming analytics and achievements with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "games")
    
    @user_games.command(name='list', aliases=['favorites', 'fav'])
    async def games_list(self, ctx, member: discord.Member = None):
        """Show all favorite games ranked by playtime with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "games_list")
    
    @user_games.command(name='history', aliases=['hist', 'log'])
    async def games_history(self, ctx, member: discord.Member = None):
        """Show complete gaming history chronologically with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "games_history")
    
    # ==================== MUSIC COMMANDS ====================
    
    @commands.group(name='music', aliases=['listening', 'spotify'], invoke_without_command=True)
    async def user_music(self, ctx, member: discord.Member = None):
        """Show user's music listening analytics and achievements with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "music")
    
    @user_music.command(name='artists', aliases=['artist', 'fav'])
    async def music_artists(self, ctx, member: discord.Member = None):
        """Show all favorite artists ranked by listening time with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "music_artists")
    
    @user_music.command(name='songs', aliases=['tracks', 'song'])
    async def music_songs(self, ctx, member: discord.Member = None):
        """Show all favorite songs ranked by listening time with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "music_songs")
    
    @user_music.command(name='history', aliases=['hist', 'log'])
    async def music_history(self, ctx, member: discord.Member = None):
        """Show complete listening history chronologically with navigation"""
        if member is None:
            member = ctx.author
        
        await self.send_profile_with_navigation(ctx, member, "music_history")
    
    async def send_profile_with_navigation(self, ctx, member, initial_view):
        """Send profile information with interactive navigation dropdown"""
        
        stats = await self.db.get_user_stats(member.id)

        if not stats:
            embed = discord.Embed(
                title="❌ No Data Found",
                description=f"Roxy hasn't seen {member.display_name} yet! Send a message first.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Use indexed access instead of unpacking to avoid the "too many values" error
        user_id = stats[0]
        username = stats[1] if len(stats) > 1 else "Unknown"
        display_name = stats[2] if len(stats) > 2 else member.display_name
        join_date = stats[3] if len(stats) > 3 else None
        total_messages = stats[4] if len(stats) > 4 else 0
        total_playtime = stats[5] if len(stats) > 5 else 0
        current_game = stats[6] if len(stats) > 6 else None
        last_seen = stats[7] if len(stats) > 7 else None
        level = stats[8] if len(stats) > 8 else 1
        xp = stats[9] if len(stats) > 9 else 0
        total_listening_time = stats[10] if len(stats) > 10 else 0
        current_song = stats[11] if len(stats) > 11 else None
        current_artist = stats[12] if len(stats) > 12 else None
        
        # Check if user is admin
        is_admin = is_admin_id(member.id)
        
        # Profile view data
        view_data = {
            "profile": {
                "emoji": "✨",
                "label": "Profile Overview",
                "description": "Complete user profile"
            },
            "level": {
                "emoji": "📊", 
                "label": "Level & XP",
                "description": "Level progression details"
            },
            "games": {
                "emoji": "🎮",
                "label": "Gaming Overview", 
                "description": "Gaming stats & achievements"
            },
            "games_list": {
                "emoji": "📋",
                "label": "Favorite Games",
                "description": "All games ranked by playtime"
            },
            "games_history": {
                "emoji": "📈",
                "label": "Gaming History",
                "description": "Complete gaming sessions"
            },
            "apps": {
                "emoji": "💻",
                "label": "Apps",
                "description": "Time in apps like VS Code, YouTube, Netflix"
            },
            "music": {
                "emoji": "🎵",
                "label": "Music Overview",
                "description": "Listening stats & achievements"
            },
            "music_artists": {
                "emoji": "🎤",
                "label": "Favorite Artists",
                "description": "All artists ranked by listening time"
            },
            "music_songs": {
                "emoji": "🎶",
                "label": "Favorite Songs",
                "description": "All songs ranked by listening time"
            },
            "music_history": {
                "emoji": "📻",
                "label": "Listening History",
                "description": "Complete listening sessions"
            }
        }
        
        current_view = initial_view
        current_page = 1  # For pagination in games_list and games_history
        
        async def create_profile_embed():
            """Create profile overview embed"""
            
            # Calculate playtime formatting
            hours = total_playtime // 3600
            minutes = (total_playtime % 3600) // 60
            
            # Calculate listening time formatting
            listening_hours = total_listening_time // 3600
            listening_minutes = (total_listening_time % 3600) // 60
            
            # Calculate progressive XP requirements
            current_level_xp = self.get_xp_for_level(level)
            next_level_xp = self.get_xp_for_level(level + 1)
            progress_xp = xp - current_level_xp
            needed_xp = next_level_xp - xp
            progress_percentage = int((progress_xp / (next_level_xp - current_level_xp)) * 100) if next_level_xp > current_level_xp else 100
            
            # Create beautiful profile embed
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {display_name}'s Profile",
                    color=0xffd700  # Gold color for admin
                )
                embed.set_author(
                    name="🔱 ROXY BOT OWNER 🔱",
                    icon_url=member.avatar.url if member.avatar else member.default_avatar.url
                )
            else:
                embed = discord.Embed(
                    title=f"✨ {display_name}'s Profile",
                    color=0x9b59b6  # Beautiful purple color
                )
            
            # Set user avatar
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # === LEVEL & XP SECTION ===
            level_emoji = self.get_level_emoji(level, is_admin)
            
            if is_admin:
                level_title = f"👑 **Level {level}** (Owner)"
            else:
                level_title = f"{level_emoji} **Level {level}**"
            
            embed.add_field(
                name=level_title,
                value=f"**Progress:** {progress_xp}/{next_level_xp - current_level_xp} ({progress_percentage}%)\n**Total XP:** {xp:,}/{next_level_xp:,}",
                inline=False
            )
            
            # === ACTIVITY STATS SECTION ===
            # Include sessions still in progress, so a call or game counts live
            ongoing = await self.db.get_ongoing_seconds(member.id)
            live_playtime = (total_playtime or 0) + ongoing['game']
            app_seconds = (await self.db.get_app_stats(member.id))['total_seconds'] + ongoing['app']
            voice_seconds = (await self.db.get_voice_stats(member.id))['total_seconds'] + ongoing['voice']
            total_tracked_seconds = live_playtime + app_seconds + (total_listening_time or 0)
            if is_admin:
                rank_title = "🔱 Bot Owner"
            else:
                rank_title = self.get_rank_title(level)

            # Left column: talking and totals - right column: where the time went
            embed.add_field(
                name="📊 **Activity**",
                value=f"📝 **{total_messages:,}** Messages\n🎙️ **{voice_seconds // 3600}h {(voice_seconds % 3600) // 60}m** Voice\n⏱️ **{total_tracked_seconds // 3600}h {(total_tracked_seconds % 3600) // 60}m** Total\n🎯 **{rank_title}**" + ("\n🛡️ **Server Admin**" if not is_admin and is_server_admin(member) else ""),
                inline=True
            )
            embed.add_field(
                name="⏱️ **Time Tracked**",
                value=f"🎮 **{live_playtime // 3600}h {(live_playtime % 3600) // 60}m** Gaming\n💻 **{app_seconds // 3600}h {(app_seconds % 3600) // 60}m** Apps\n🎵 **{listening_hours}h {listening_minutes}m** Listening",
                inline=True
            )

            # === CURRENT STATUS SECTION ===
            status_lines = []

            if current_game:
                status_lines.append(f"🎮 Playing **{current_game}**")

            current_app = self.bot.active_apps.get(member.id)
            if current_app:
                status_lines.append(f"💻 Using **{current_app}**")

            if current_song and current_artist:
                status_lines.append(f"🎵 Listening to **{current_song}** by **{current_artist}**")

            if member.id in self.bot.active_voice:
                status_lines.append("🎙️ In a voice call")

            if not status_lines:
                if is_admin:
                    status_lines.append("💤 Managing Roxy Bot 🔧")
                else:
                    status_lines.append("💤 Offline")

            if is_admin:
                status_text = "\n".join(status_lines) + " 👑"
            else:
                status_text = "\n".join(status_lines)

            embed.add_field(
                name="🔴 **Live Status**",
                value=status_text,
                inline=False
            )
            
            # === TIMELINE SECTION ===
            if join_date and last_seen:
                try:
                    join_dt = datetime.fromisoformat(join_date)
                    last_seen_dt = datetime.fromisoformat(last_seen)
                    days_tracked = (datetime.now() - join_dt).days
                    
                    timeline_info = f"""
                    📅 **{days_tracked}** days tracked
                    👁️ Last seen <t:{int(last_seen_dt.timestamp())}:R>
                    """
                    
                    embed.add_field(
                        name="⏰ **Timeline**",
                        value=timeline_info.strip(),
                        inline=False
                    )
                except Exception as e:
                    print(f"❌ Error parsing timeline dates: {e}")
            
            # === ACHIEVEMENTS SECTION ===
            achievements = self.get_achievements(level, total_messages, hours, listening_hours, is_admin,
                                                 voice_hours=voice_seconds // 3600, app_hours=app_seconds // 3600)
            if achievements:
                embed.add_field(
                    name="🏆 **Recent Achievements**",
                    value=achievements,
                    inline=False
                )

            # Achievements granted by the admin with rr ach give
            special_achievements = await self.db.get_user_custom_achievements(member.id)
            if special_achievements:
                embed.add_field(
                    name="🎖️ **Special Achievements**",
                    value="\n".join(f"• {name}" for name, _ in special_achievements)[:1024],
                    inline=False
                )

            # Patreon supporter badges (and the VIP title)
            patron_tier = get_patron_tier(self.bot, member.id)
            if patron_tier:
                badge_text = " • ".join(patron_tier['badges'])
                if patron_tier['title']:
                    badge_text = f"**{patron_tier['title']}**\n{badge_text}"
                embed.add_field(name="💜 **Patreon Supporter**", value=badge_text, inline=False)

            # === FOOTER ===
            if is_admin:
                embed.set_footer(
                    text=f"👑 Roxy Bot Owner • Ultimate Authority",
                    icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
                )
            else:
                embed.set_footer(
                    text=f"💜 Roxy Bot • Use dropdown to switch views",
                    icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
                )
            
            # Add member status badge for non-admins
            if not is_admin:
                if level >= 10:
                    embed.set_author(
                        name="🌟 Distinguished Member",
                        icon_url=member.avatar.url if member.avatar else member.default_avatar.url
                    )
                elif level >= 5:
                    embed.set_author(
                        name="⭐ Active Member", 
                        icon_url=member.avatar.url if member.avatar else member.default_avatar.url
                    )
            
            return embed
        
        async def create_level_embed():
            """Create level & XP embed"""
            
            # Calculate progressive XP requirements
            current_level_xp = self.get_xp_for_level(level)
            next_level_xp = self.get_xp_for_level(level + 1)
            progress_xp = xp - current_level_xp
            progress_percentage = int((progress_xp / (next_level_xp - current_level_xp)) * 100) if next_level_xp > current_level_xp else 100
            
            level_emoji = self.get_level_emoji(level, is_admin)
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Level (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"{level_emoji} {member.display_name}'s Level",
                    color=0xf1c40f
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            level_size = next_level_xp - current_level_xp
            embed.add_field(
                name="📊 **Current Progress**",
                value=f"**Level:** {level}\n"
                      f"**Progress:** {progress_xp}/{level_size} ({progress_percentage}%)\n"
                      f"**Total XP:** {xp:,}/{next_level_xp:,}",
                inline=False
            )

            # Show XP sources breakdown (same rates as live tracking, before Patreon boosts)
            app_seconds = (await self.db.get_app_stats(member.id))['total_seconds']
            voice_stats = await self.db.get_voice_stats(member.id)
            voice_seconds = voice_stats['total_seconds']
            message_xp = total_messages * MESSAGE_XP
            voice_xp = voice_stats['xp_minutes'] * VOICE_XP_PER_MINUTE  # Only active minutes earn voice XP
            gaming_xp = (total_playtime // 60) * GAMING_XP_PER_MINUTE
            app_xp = (app_seconds // 60) * APP_XP_PER_MINUTE
            listening_xp = (total_listening_time // 120) * LISTENING_XP_PER_2_MINUTES

            def hm(seconds):
                return f"{seconds // 3600}h {(seconds % 3600) // 60}m"

            sources = (
                f"💬 **Messages:** {message_xp:,} XP ({total_messages:,} messages)\n"
                f"🎙️ **Voice:** {voice_xp:,} XP ({hm(voice_seconds)})\n"
                f"🎮 **Gaming:** {gaming_xp:,} XP ({hm(total_playtime)})\n"
                f"💻 **Apps:** {app_xp:,} XP ({hm(app_seconds)})\n"
                f"🎵 **Listening:** {listening_xp:,} XP ({hm(total_listening_time)})"
            )
            bonus_xp = xp - (message_xp + voice_xp + gaming_xp + app_xp + listening_xp)
            if bonus_xp > 0:
                sources += f"\n✨ **Other:** {bonus_xp:,} XP (boosts & small bonuses)"

            embed.add_field(name="✨ **XP Sources**", value=sources, inline=False)
            
            # Show XP requirements for next few levels
            next_levels = []
            for i in range(1, 4):
                future_level = level + i
                future_xp = self.get_xp_for_level(future_level)
                xp_needed = future_xp - xp
                if xp_needed > 0:
                    next_levels.append(f"Level {future_level}: {xp_needed:,} XP")
            
            if next_levels:
                embed.add_field(
                    name="🎯 **Upcoming Levels**",
                    value="\n".join(next_levels),
                    inline=False
                )
            
            if is_admin:
                embed.set_footer(text="👑 Keep being an awesome owner! • Use dropdown to switch views")
            else:
                embed.set_footer(text="💜 Chat, join voice, game and listen to level up! • Use dropdown to switch views")
            
            return embed
        
        async def create_music_embed():
            """Create music listening overview embed"""
            
            listening_hours = total_listening_time // 3600
            listening_minutes = (total_listening_time % 3600) // 60
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Music (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"🎵 {member.display_name}'s Music",
                    color=0x1db954  # Spotify green
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Current status
            if current_song and current_artist:
                if is_admin:
                    status_text = f"🟢 **Currently listening:** {current_song} by {current_artist} 👑"
                else:
                    status_text = f"🟢 **Currently listening:** {current_song} by {current_artist}"
            else:
                if is_admin:
                    status_text = "⚪ **Status:** Managing Roxy Bot 🔧"
                else:
                    status_text = "⚪ **Status:** Not listening to music"
            
            embed.add_field(
                name="🔴 **Live Status**",
                value=status_text,
                inline=False
            )
            
            # Music stats
            music_rank = self.get_music_rank(listening_hours)
            if is_admin:
                music_rank = f"👑 {music_rank}"
            
            # Get listening statistics
            listening_stats = await self.db.get_listening_statistics(member.id)
            avg_session = listening_stats['avg_session']
            total_sessions = listening_stats['total_sessions']
            longest_session = listening_stats['longest_session']
                
            embed.add_field(
                name="📊 **Listening Stats**",
                value=f"""
                🕐 **Total Listening Time:** {listening_hours}h {listening_minutes}m
                🎯 **Music Rank:** {music_rank}
                📈 **XP from Listening:** {total_listening_time // 120} XP
                🎲 **Total Sessions:** {total_sessions}
                ⏱️ **Avg Session:** {avg_session}
                🏆 **Longest Session:** {longest_session}
                """.strip(),
                inline=False
            )
            
            # Get favorite artists (Top 3 only)
            favorite_artists = await self.db.get_favorite_artists(member.id, 3)
            if favorite_artists:
                artists_text = ""
                for i, (artist, listening_time, sessions) in enumerate(favorite_artists, 1):
                    artist_hours = listening_time // 3600
                    artist_minutes = (listening_time % 3600) // 60
                    artists_text += f"**{i}.** {artist} - {artist_hours}h {artist_minutes}m ({sessions} sessions)\n"
                
                embed.add_field(
                    name="🎤 **Top 3 Favorite Artists**",
                    value=artists_text.strip(),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎤 **Top 3 Favorite Artists**",
                    value="No music listened to yet",
                    inline=False
                )
            
            # Get recent listening history (Latest 5 only)
            recent_music = await self.db.get_recent_listening_history(member.id, 5)
            if recent_music:
                history_text = ""
                for song_title, artist_name, album_name, last_played, duration in recent_music:
                    music_minutes = duration // 60
                    music_seconds = duration % 60
                    time_ago = f"<t:{int(last_played.timestamp())}:R>"
                    history_text += f"• **{song_title}** by *{artist_name}* - {format_duration(duration)} ({time_ago})\n"
                
                embed.add_field(
                    name="📈 **Latest 5 Tracks**",
                    value=history_text.strip(),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📈 **Latest 5 Tracks**",
                    value="No recent listening history",
                    inline=False
                )
            
            # Get music achievements
            music_achievements = self.get_music_achievements(listening_hours, total_sessions, listening_stats['longest_session_minutes'], is_admin)
            if music_achievements:
                embed.add_field(
                    name="🏆 **Music Achievements**",
                    value=music_achievements,
                    inline=False
                )
            else:
                # If no achievements from the helper method, try getting from database
                db_achievements = await self.db.get_user_music_achievements(member.id)
                if db_achievements:
                    # Show top 3 achievements
                    achievement_text = "\n".join([f"• {achievement}" for achievement in db_achievements[:3]])
                    embed.add_field(
                        name="🏆 **Music Achievements**",
                        value=achievement_text,
                        inline=False
                    )
            
            embed.set_footer(text="💜 Roxy tracks all your Spotify listening! • Use dropdown to switch views")
            
            return embed
        
        async def create_games_embed():
            """Create gaming overview embed"""
            
            hours = total_playtime // 3600
            minutes = (total_playtime % 3600) // 60
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Gaming (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"🎮 {member.display_name}'s Gaming",
                    color=0x9b59b6
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Current status
            if current_game:
                if is_admin:
                    status_text = f"🟢 **Currently playing:** {current_game} 👑"
                else:
                    status_text = f"🟢 **Currently playing:** {current_game}"
            else:
                if is_admin:
                    status_text = "⚪ **Status:** Managing Roxy Bot 🔧"
                else:
                    status_text = "⚪ **Status:** Not gaming"
            
            embed.add_field(
                name="🔴 **Live Status**",
                value=status_text,
                inline=False
            )
            
            # Gaming stats
            gaming_rank = self.get_gaming_rank(hours)
            if is_admin:
                gaming_rank = f"👑 {gaming_rank}"
            
            # Get session statistics
            session_stats = await self.db.get_session_statistics(member.id)
            avg_session = session_stats['avg_session']
            total_sessions = session_stats['total_sessions']
            longest_session = session_stats['longest_session']
                
            embed.add_field(
                name="📊 **Gaming Stats**",
                value=f"""
                🕐 **Total Playtime:** {hours}h {minutes}m
                🎯 **Gaming Rank:** {gaming_rank}
                📈 **XP from Gaming:** {total_playtime // 60} XP
                🎲 **Total Sessions:** {total_sessions}
                ⏱️ **Avg Session:** {avg_session}
                🏆 **Longest Session:** {longest_session}
                """.strip(),
                inline=False
            )
            
            # Get favorite games (Top 3 only)
            favorite_games = await self.db.get_favorite_games(member.id, 3)
            if favorite_games:
                fav_text = ""
                for i, (game, playtime, sessions) in enumerate(favorite_games, 1):
                    game_hours = playtime // 3600
                    game_minutes = (playtime % 3600) // 60
                    fav_text += f"**{i}.** {game} - {game_hours}h {game_minutes}m ({sessions} sessions)\n"
                
                embed.add_field(
                    name="🎮 **Top 3 Favorite Games**",
                    value=fav_text.strip(),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎮 **Top 3 Favorite Games**",
                    value="No games played yet",
                    inline=False
                )
            
            # Get recent game history (Latest 5 only)
            recent_games = await self.db.get_recent_game_history(member.id, 5)
            if recent_games:
                history_text = ""
                for game, last_played, duration in recent_games:
                    game_minutes = duration // 60
                    game_seconds = duration % 60
                    time_ago = f"<t:{int(last_played.timestamp())}:R>"
                    history_text += f"• **{game}** - {format_duration(duration)} ({time_ago})\n"
                
                embed.add_field(
                    name="📈 **Latest 5 Games**",
                    value=history_text.strip(),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📈 **Latest 5 Games**",
                    value="No recent games",
                    inline=False
                )
            
            # Get gaming achievements
            gaming_achievements = self.get_gaming_achievements(hours, total_sessions, session_stats['longest_session_minutes'], is_admin)
            if gaming_achievements:
                embed.add_field(
                    name="🏆 **Gaming Achievements**",
                    value=gaming_achievements,
                    inline=False
                )
            else:
                # If no achievements from the helper method, try getting from database
                db_achievements = await self.db.get_user_gaming_achievements(member.id)
                if db_achievements:
                    # Show top 3 achievements
                    achievement_text = "\n".join([f"• {achievement}" for achievement in db_achievements[:3]])
                    embed.add_field(
                        name="🏆 **Gaming Achievements**",
                        value=achievement_text,
                        inline=False
                    )
            
            embed.set_footer(text="💜 Roxy tracks all your gaming activities! • Use dropdown to switch views")
            
            return embed
        
        async def create_games_list_embed(page=1):
            """Create games list embed with pagination"""
            # Get all favorite games
            favorite_games = await self.db.get_favorite_games(member.id, 100)
            
            if not favorite_games:
                embed = discord.Embed(
                    title=f"🎮 {member.display_name}'s Game List",
                    description="No games played yet!",
                    color=0x9b59b6
                )
                embed.set_footer(text="💜 Use dropdown to switch views")
                return embed, 1, 1
            
            # Pagination setup
            games_per_page = 10
            total_pages = (len(favorite_games) + games_per_page - 1) // games_per_page
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Complete Game List (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"🎮 {member.display_name}'s Complete Game List",
                    color=0x9b59b6
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Get games for this page
            start_index = (page - 1) * games_per_page
            end_index = start_index + games_per_page
            page_games = favorite_games[start_index:end_index]
            
            # Build games text
            games_text = ""
            for i, (game, playtime, sessions) in enumerate(page_games, start_index + 1):
                game_hours = playtime // 3600
                game_minutes = (playtime % 3600) // 60
                games_text += f"{i}. **{game}** - {game_hours}h {game_minutes}m ({sessions} sessions)\n"
            
            embed.add_field(
                name=f"All Games Ranked by Playtime (Page {page}/{total_pages})",
                value=self.fit_field(games_text.strip()),
                inline=False
            )
            
            # Add summary stats
            total_games = len(favorite_games)
            total_playtime_all = sum(game[1] for game in favorite_games)
            total_sessions_all = sum(game[2] for game in favorite_games)
            total_hours = total_playtime_all // 3600
            total_minutes = (total_playtime_all % 3600) // 60
            
            # Show page stats
            page_playtime = sum(game[1] for game in page_games)
            page_sessions = sum(game[2] for game in page_games)
            page_hours = page_playtime // 3600
            page_mins = (page_playtime % 3600) // 60
            
            embed.add_field(
                name="📈 **Summary**",
                value=f"🎮 **{len(page_games)}** games shown (of {total_games} total)\n⏱️ **{page_hours}h {page_mins}m** on this page\n🎲 **{page_sessions}** sessions on this page\n🏆 **{total_hours}h {total_minutes}m** total playtime ({total_sessions_all} total sessions)",
                inline=False
            )
            
            if total_pages > 1:
                embed.set_footer(text=f"💜 Page {page} of {total_pages} • Use ⬅️ ➡️ and dropdown to navigate")
            else:
                embed.set_footer(text="💜 Complete games list • Use dropdown to switch views")
            
            return embed, page, total_pages
        
        async def create_games_history_embed(page=1):
            """Create games history embed with pagination"""
            # Get all game history
            game_history = await self.db.get_recent_game_history(member.id, 100)
            
            if not game_history:
                embed = discord.Embed(
                    title=f"📈 {member.display_name}'s Gaming History",
                    description="No gaming sessions recorded yet!",
                    color=0x9b59b6
                )
                embed.set_footer(text="💜 Use dropdown to switch views")
                return embed, 1, 1
            
            # Pagination setup
            sessions_per_page = 10
            total_pages = (len(game_history) + sessions_per_page - 1) // sessions_per_page
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Gaming History (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"📈 {member.display_name}'s Gaming History",
                    color=0x9b59b6
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Get sessions for this page
            start_index = (page - 1) * sessions_per_page
            end_index = start_index + sessions_per_page
            page_history = game_history[start_index:end_index]
            
            # Build history text
            history_text = ""
            for i, (game, end_time, duration) in enumerate(page_history, start_index + 1):
                game_minutes = duration // 60
                game_seconds = duration % 60
                time_ago = f"<t:{int(end_time.timestamp())}:R>"
                history_text += f"• **{game}** - {format_duration(duration)} ({time_ago})\n"
            
            embed.add_field(
                name=f"Recent Gaming Sessions (Page {page}/{total_pages})",
                value=self.fit_field(history_text.strip()),
                inline=False
            )
            
            # Add summary for this page
            page_total_time = sum(session[2] for session in page_history)
            page_hours = page_total_time // 3600
            page_minutes = (page_total_time % 3600) // 60
            
            # Get total summary
            total_sessions = len(game_history)
            total_time = sum(session[2] for session in game_history)
            total_hours = total_time // 3600
            total_mins = (total_time % 3600) // 60
            
            embed.add_field(
                name="📊 **Summary**",
                value=f"🎲 **{len(page_history)}** sessions shown (of {total_sessions} total)\n⏱️ **{page_hours}h {page_minutes}m** on this page\n🏆 **{total_hours}h {total_mins}m** total gaming time",
                inline=False
            )
            
            if total_pages > 1:
                embed.set_footer(text=f"💜 Page {page} of {total_pages} • Use ⬅️ ➡️ and dropdown to navigate")
            else:
                embed.set_footer(text="💜 Complete gaming history • Use dropdown to switch views")
            
            return embed, page, total_pages
        
        # ==================== MUSIC EMBED FUNCTIONS ====================
        
        async def create_music_artists_embed(page=1):
            """Create music artists list embed with pagination"""
            # Get all favorite artists
            favorite_artists = await self.db.get_favorite_artists(member.id, 100)
            
            if not favorite_artists:
                embed = discord.Embed(
                    title=f"🎤 {member.display_name}'s Artist List",
                    description="No artists listened to yet!",
                    color=0x1db954
                )
                embed.set_footer(text="💜 Use dropdown to switch views")
                return embed, 1, 1
            
            # Pagination setup
            artists_per_page = 10
            total_pages = (len(favorite_artists) + artists_per_page - 1) // artists_per_page
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Complete Artist List (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"🎤 {member.display_name}'s Complete Artist List",
                    color=0x1db954
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Get artists for this page
            start_index = (page - 1) * artists_per_page
            end_index = start_index + artists_per_page
            page_artists = favorite_artists[start_index:end_index]
            
            # Build artists text
            artists_text = ""
            for i, (artist, listening_time, sessions) in enumerate(page_artists, start_index + 1):
                artist_hours = listening_time // 3600
                artist_minutes = (listening_time % 3600) // 60
                artists_text += f"{i}. **{artist}** - {artist_hours}h {artist_minutes}m ({sessions} sessions)\n"
            
            embed.add_field(
                name=f"All Artists Ranked by Listening Time (Page {page}/{total_pages})",
                value=self.fit_field(artists_text.strip()),
                inline=False
            )
            
            # Add summary stats
            total_artists = len(favorite_artists)
            total_listening_time_all = sum(artist[1] for artist in favorite_artists)
            total_sessions_all = sum(artist[2] for artist in favorite_artists)
            total_hours = total_listening_time_all // 3600
            total_minutes = (total_listening_time_all % 3600) // 60
            
            # Show page stats
            page_listening_time = sum(artist[1] for artist in page_artists)
            page_sessions = sum(artist[2] for artist in page_artists)
            page_hours = page_listening_time // 3600
            page_mins = (page_listening_time % 3600) // 60
            
            embed.add_field(
                name="📈 **Summary**",
                value=f"🎤 **{len(page_artists)}** artists shown (of {total_artists} total)\n⏱️ **{page_hours}h {page_mins}m** on this page\n🎲 **{page_sessions}** sessions on this page\n🏆 **{total_hours}h {total_minutes}m** total listening time ({total_sessions_all} total sessions)",
                inline=False
            )
            
            if total_pages > 1:
                embed.set_footer(text=f"💜 Page {page} of {total_pages} • Use ⬅️ ➡️ and dropdown to navigate")
            else:
                embed.set_footer(text="💜 Complete artists list • Use dropdown to switch views")
            
            return embed, page, total_pages
        
        async def create_music_songs_embed(page=1):
            """Create music songs list embed with pagination"""
            # Get all favorite songs
            favorite_songs = await self.db.get_favorite_songs(member.id, 100)
            
            if not favorite_songs:
                embed = discord.Embed(
                    title=f"🎶 {member.display_name}'s Song List",
                    description="No songs listened to yet!",
                    color=0x1db954
                )
                embed.set_footer(text="💜 Use dropdown to switch views")
                return embed, 1, 1
            
            # Pagination setup
            songs_per_page = 10
            total_pages = (len(favorite_songs) + songs_per_page - 1) // songs_per_page
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Complete Song List (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"🎶 {member.display_name}'s Complete Song List",
                    color=0x1db954
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Get songs for this page
            start_index = (page - 1) * songs_per_page
            end_index = start_index + songs_per_page
            page_songs = favorite_songs[start_index:end_index]
            
            # Build songs text
            songs_text = ""
            for i, (song_title, artist_name, listening_time, play_count) in enumerate(page_songs, start_index + 1):
                song_hours = listening_time // 3600
                song_minutes = (listening_time % 3600) // 60
                songs_text += f"{i}. **{song_title}** by *{artist_name}* - {song_hours}h {song_minutes}m ({play_count} plays)\n"
            
            embed.add_field(
                name=f"All Songs Ranked by Listening Time (Page {page}/{total_pages})",
                value=self.fit_field(songs_text.strip()),
                inline=False
            )
            
            # Add summary stats
            total_songs = len(favorite_songs)
            total_listening_time_all = sum(song[2] for song in favorite_songs)
            total_plays_all = sum(song[3] for song in favorite_songs)
            total_hours = total_listening_time_all // 3600
            total_minutes = (total_listening_time_all % 3600) // 60
            
            # Show page stats
            page_listening_time = sum(song[2] for song in page_songs)
            page_plays = sum(song[3] for song in page_songs)
            page_hours = page_listening_time // 3600
            page_mins = (page_listening_time % 3600) // 60
            
            embed.add_field(
                name="📈 **Summary**",
                value=f"🎶 **{len(page_songs)}** songs shown (of {total_songs} total)\n⏱️ **{page_hours}h {page_mins}m** on this page\n🎵 **{page_plays}** plays on this page\n🏆 **{total_hours}h {total_minutes}m** total listening time ({total_plays_all} total plays)",
                inline=False
            )
            
            if total_pages > 1:
                embed.set_footer(text=f"💜 Page {page} of {total_pages} • Use ⬅️ ➡️ and dropdown to navigate")
            else:
                embed.set_footer(text="💜 Complete songs list • Use dropdown to switch views")
            
            return embed, page, total_pages
        
        async def create_music_history_embed(page=1):
            """Create music history embed with pagination"""
            # Get all listening history
            listening_history = await self.db.get_recent_listening_history(member.id, 100)
            
            if not listening_history:
                embed = discord.Embed(
                    title=f"📻 {member.display_name}'s Listening History",
                    description="No listening sessions recorded yet!",
                    color=0x1db954
                )
                embed.set_footer(text="💜 Use dropdown to switch views")
                return embed, 1, 1
            
            # Pagination setup
            sessions_per_page = 10
            total_pages = (len(listening_history) + sessions_per_page - 1) // sessions_per_page
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Listening History (Owner)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"📻 {member.display_name}'s Listening History",
                    color=0x1db954
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Get sessions for this page
            start_index = (page - 1) * sessions_per_page
            end_index = start_index + sessions_per_page
            page_history = listening_history[start_index:end_index]
            
            # Build history text
            history_text = ""
            for i, (song_title, artist_name, album_name, end_time, duration) in enumerate(page_history, start_index + 1):
                music_minutes = duration // 60
                music_seconds = duration % 60
                time_ago = f"<t:{int(end_time.timestamp())}:R>"
                album_text = f" ({album_name})" if album_name else ""
                history_text += f"• **{song_title}** by *{artist_name}*{album_text} - {format_duration(duration)} ({time_ago})\n"
            
            embed.add_field(
                name=f"Recent Listening Sessions (Page {page}/{total_pages})",
                value=self.fit_field(history_text.strip()),
                inline=False
            )
            
            # Add summary for this page
            page_total_time = sum(session[4] for session in page_history)
            page_hours = page_total_time // 3600
            page_minutes = (page_total_time % 3600) // 60
            
            # Get total summary
            total_sessions = len(listening_history)
            total_time = sum(session[4] for session in listening_history)
            total_hours = total_time // 3600
            total_mins = (total_time % 3600) // 60
            
            embed.add_field(
                name="📊 **Summary**",
                value=f"🎵 **{len(page_history)}** sessions shown (of {total_sessions} total)\n⏱️ **{page_hours}h {page_minutes}m** on this page\n🏆 **{total_hours}h {total_mins}m** total listening time",
                inline=False
            )
            
            if total_pages > 1:
                embed.set_footer(text=f"💜 Page {page} of {total_pages} • Use ⬅️ ➡️ and dropdown to navigate")
            else:
                embed.set_footer(text="💜 Complete listening history • Use dropdown to switch views")
            
            return embed, page, total_pages
        
        # Create view with navigation - Fixed implementation with proper state management
        class ProfileView(discord.ui.View):
            def __init__(self, current_view_val, current_page_val, total_pages_val):
                super().__init__(timeout=300)
                self.current_view = current_view_val
                self.current_page = current_page_val
                self.total_pages = total_pages_val
                
                # Add dropdown
                self.add_item(ProfileSelect(self.current_view))
                
                # Add pagination buttons for paginated views
                paginated_views = ["games_list", "games_history", "music_artists", "music_songs", "music_history"]
                if self.current_view in paginated_views and self.total_pages > 1:
                    self.add_item(PreviousButton(self.current_page <= 1))
                    self.add_item(NextButton(self.current_page >= self.total_pages))
                
                self.add_item(CloseButton())
            
            async def update_view(self, interaction, new_view=None, new_page=None):
                """Update the view with new state"""
                nonlocal current_view, current_page
                
                if new_view is not None:
                    current_view = new_view
                    current_page = 1  # Reset page when switching views
                elif new_page is not None:
                    current_page = new_page
                
                embed, page, total_pages = await get_current_embed()
                current_page = page  # Update the actual current page
                
                # Create new view with updated state
                view = ProfileView(current_view, current_page, total_pages)
                await interaction.response.edit_message(embed=embed, view=view)
        
        # Component classes
        class ProfileSelect(discord.ui.Select):
            def __init__(self, current_view_val):
                options = []
                for view_key, view_info in view_data.items():
                    options.append(
                        discord.SelectOption(
                            label=view_info["label"],
                            description=view_info["description"],
                            emoji=view_info["emoji"],
                            value=view_key,
                            default=(view_key == current_view_val)
                        )
                    )
                
                super().__init__(
                    placeholder="💜 Choose a view...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(self, interaction):
                await self.view.update_view(interaction, new_view=self.values[0])
        
        class PreviousButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(label='◀️ Previous', style=discord.ButtonStyle.secondary, disabled=disabled)
            
            async def callback(self, interaction):
                if self.view.current_page > 1:
                    await self.view.update_view(interaction, new_page=self.view.current_page - 1)
        
        class NextButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(label='▶️ Next', style=discord.ButtonStyle.secondary, disabled=disabled)
            
            async def callback(self, interaction):
                if self.view.current_page < self.view.total_pages:
                    await self.view.update_view(interaction, new_page=self.view.current_page + 1)
        
        class CloseButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label='❌ Close', style=discord.ButtonStyle.danger)
            
            async def callback(self, interaction):
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="💜 Profile Menu Closed",
                        description="Use profile commands to view again.",
                        color=discord.Color.red()
                    ),
                    view=None
                )
        
        async def get_current_embed():
            """Get embed for current view"""
            if current_view == "profile":
                return await create_profile_embed(), 1, 1
            elif current_view == "level":
                return await create_level_embed(), 1, 1
            elif current_view == "games":
                return await create_games_embed(), 1, 1
            elif current_view == "games_list":
                return await create_games_list_embed(current_page)
            elif current_view == "games_history":
                return await create_games_history_embed(current_page)
            elif current_view == "apps":
                return await self.build_apps_embed(member), 1, 1
            elif current_view == "music":
                return await create_music_embed(), 1, 1
            elif current_view == "music_artists":
                return await create_music_artists_embed(current_page)
            elif current_view == "music_songs":
                return await create_music_songs_embed(current_page)
            elif current_view == "music_history":
                return await create_music_history_embed(current_page)
        
        # Send initial embed
        embed, page, total_pages = await get_current_embed()
        current_page = page
        view = ProfileView(current_view, current_page, total_pages)
        
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name='top', aliases=['leaderboard', 'lb'])
    @commands.guild_only()
    async def leaderboard(self, ctx, category='messages'):
        """Roxy's leaderboards with category dropdown, pages and a server/global toggle"""
        category = category.lower()
        categories = {
            'messages': {'label': 'Messages', 'emoji': '💬', 'tip': 'Stay active in chat to climb!'},
            'voice': {'label': 'Voice', 'emoji': '🎙️', 'tip': 'Hang out in voice channels to climb!'},
            'playtime': {'label': 'Playtime', 'emoji': '🎮', 'tip': 'Game more to reach the top!'},
            'apps': {'label': 'Apps', 'emoji': '💻', 'tip': 'Time in apps like VS Code and YouTube counts!'},
            'listening': {'label': 'Listening', 'emoji': '🎵', 'tip': 'Listen to more music to climb!'},
            'level': {'label': 'Level', 'emoji': '⭐', 'tip': 'Balance all activities!'},
        }
        # 'xp' still works when typed, it just isn't in the dropdown
        extra_categories = {'xp': {'label': 'XP', 'emoji': '✨', 'tip': 'Earn XP through all activities!'}}
        all_categories = {**categories, **extra_categories}

        if category not in all_categories:
            embed = discord.Embed(
                title="❌ Invalid Category",
                description=f"**Valid categories:** {', '.join(all_categories)}",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return

        PAGE_SIZE = 10
        guild = ctx.guild
        bot = self.bot
        db = self.db
        state = {'category': category, 'page': 1, 'global': False}

        async def get_rows():
            """All ranked (user_id, name, value) rows for the current category and scope"""
            leaderboard_data = await db.get_leaderboard(state['category'], 100000)
            rows = []
            for user_id, username, display_name, value in leaderboard_data:
                if state['global']:
                    user = bot.get_user(user_id)
                    rows.append((user_id, user.display_name if user else (display_name or username), value))
                else:
                    # The database covers every server Roxy is in - keep only this server's members
                    member = guild.get_member(user_id)
                    if member:
                        rows.append((user_id, member.display_name, value))
            return rows

        async def create_leaderboard_embed():
            info = all_categories[state['category']]
            rows = await get_rows()
            total_pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
            state['page'] = min(max(state['page'], 1), total_pages)
            state['total_pages'] = total_pages

            scope = "🌍 Global" if state['global'] else f"🏠 {guild.name}"
            embed = discord.Embed(
                title=f"🏆 {info['emoji']} {info['label']} Leaderboard",
                description=f"**Top performers • {scope}**",
                color=0x3498db if state['global'] else 0xffd700
            )

            start = (state['page'] - 1) * PAGE_SIZE
            medals = ["🥇", "🥈", "🥉"]
            leaderboard_text = ""
            for rank, (user_id, name, value) in enumerate(rows[start:start + PAGE_SIZE], start=start + 1):
                # Add crown for admin
                if is_admin_id(user_id):
                    name = f"👑 {name}"

                # Format value based on category
                if state['category'] in ['playtime', 'listening', 'voice', 'apps']:
                    formatted_value = f"{value // 3600}h {(value % 3600) // 60}m"
                elif state['category'] in ['xp', 'messages']:
                    formatted_value = f"{value:,}"
                else:
                    formatted_value = f"Level {value}"

                if rank <= 3:
                    leaderboard_text += f"{medals[rank - 1]} **{name}** • `{formatted_value}`\n"
                else:
                    leaderboard_text += f"`#{rank:2}` **{name}** • `{formatted_value}`\n"

            embed.add_field(
                name=f"📊 **Rankings {start + 1}-{start + PAGE_SIZE}**" if rows else "📊 **Rankings**",
                value=leaderboard_text or "No data for this category yet.",
                inline=False
            )

            # Show the command user's own rank
            your_rank = next((i for i, row in enumerate(rows, start=1) if row[0] == ctx.author.id), None)
            if your_rank:
                embed.add_field(name="📍 **Your Rank**", value=f"#{your_rank} of {len(rows)}", inline=False)

            embed.set_footer(
                text=f"Page {state['page']}/{total_pages} • 💜 {info['tip']}",
                icon_url=bot.user.display_avatar.url
            )
            return embed

        class LeaderboardSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=info['label'], emoji=info['emoji'], value=key, default=(key == state['category']))
                    for key, info in categories.items()
                ]
                super().__init__(placeholder="🏆 Choose a leaderboard...", min_values=1, max_values=1, options=options, row=0)

            async def callback(self, interaction):
                state['category'] = self.values[0]
                state['page'] = 1  # New category starts at the top
                await self.view.refresh(interaction)

        class LeaderboardView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.add_item(LeaderboardSelect())
                self.previous_page.disabled = state['page'] <= 1
                self.next_page.disabled = state['page'] >= state['total_pages']
                self.toggle_scope.label = "🏠 Server" if state['global'] else "🌍 Global"

            async def refresh(self, interaction):
                embed = await create_leaderboard_embed()
                new_view = LeaderboardView()
                new_view.message = interaction.message
                self.stop()  # Only the newest view stays alive
                await interaction.response.edit_message(embed=embed, view=new_view)

            @discord.ui.button(label='◀️ Previous', style=discord.ButtonStyle.secondary, row=1)
            async def previous_page(self, interaction, button):
                state['page'] -= 1
                await self.refresh(interaction)

            @discord.ui.button(label='▶️ Next', style=discord.ButtonStyle.secondary, row=1)
            async def next_page(self, interaction, button):
                state['page'] += 1
                await self.refresh(interaction)

            @discord.ui.button(label='🌍 Global', style=discord.ButtonStyle.primary, row=1)
            async def toggle_scope(self, interaction, button):
                state['global'] = not state['global']
                state['page'] = 1
                await self.refresh(interaction)

            @discord.ui.button(label='❌ Close', style=discord.ButtonStyle.danger, row=1)
            async def close_menu(self, interaction, button):
                self.stop()
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="🏆 Leaderboard Closed",
                        description="Use `rr top` to open again.",
                        color=discord.Color.red()
                    ),
                    view=None
                )

            async def interaction_check(self, interaction):
                # Only the person who ran the command can use their leaderboard menu
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ This menu isn't yours - use `rr top` to get your own.", ephemeral=True)
                    return False
                return True

            async def on_timeout(self):
                try:
                    await self.message.edit(view=None)
                except (AttributeError, discord.HTTPException):
                    pass

        embed = await create_leaderboard_embed()
        view = LeaderboardView()
        view.message = await ctx.send(embed=embed, view=view)

    @commands.command(name='serverinfo')
    @commands.guild_only()
    async def server_info(self, ctx, *, extra: str = None):
        """Discord information about this server (no server IDs - only the server you're in)"""
        embed = server_overview_embed(ctx.guild)
        if extra:
            embed.set_footer(text="ℹ️ Server IDs aren't allowed - rr serverinfo always shows the server you're in")
        else:
            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='userinfo', aliases=['profileinfo', 'userprofile', 'whois'], description="Discord profile info: Server and Global views")
    @app_commands.describe(member="Whose Discord profile to show (default: you)")
    @app_commands.guild_only()
    @commands.guild_only()
    async def profile_info(self, ctx, member: discord.Member = None):
        """Discord profile information for you or a member of this server - Server and Global views"""
        await ctx.defer()  # Slash commands must answer within 3 seconds - this buys time
        member = member or ctx.author
        try:
            # Raw API data: banner and accent color, plus nameplate/name style/tag that discord.py 2.5 doesn't parse
            raw = await self.bot.http.get_user(member.id)
            user = discord.User(state=self.bot._connection, data=raw)
        except discord.HTTPException:
            raw, user = None, None

        views = {
            'server': {'label': 'Server', 'emoji': '🏠', 'description': f'Profile in {ctx.guild.name}'[:100]},
            'global': {'label': 'Global', 'emoji': '🌍', 'description': 'Badges, nameplate, decoration, name style, banner'},
        }

        def create_embed(view_key):
            if view_key == 'global' and user:
                embed = global_profile_embed(user, raw)
            else:
                embed = profile_embed(member, user)
            embed.set_footer(text=f"Requested by {ctx.author.display_name} • Use rr profile for Roxy stats", icon_url=ctx.author.display_avatar.url)
            return embed

        class ProfileInfoSelect(discord.ui.Select):
            def __init__(self, current):
                options = [
                    discord.SelectOption(label=info['label'], emoji=info['emoji'], description=info['description'], value=key, default=(key == current))
                    for key, info in views.items()
                ]
                super().__init__(placeholder="👤 Choose a view...", min_values=1, max_values=1, options=options, row=0)

            async def callback(self, interaction):
                new_view = ProfileInfoView(self.values[0])
                new_view.message = interaction.message
                self.view.stop()  # Only the newest view stays alive
                await interaction.response.edit_message(embed=create_embed(self.values[0]), view=new_view)

        class ProfileInfoView(discord.ui.View):
            def __init__(self, current):
                super().__init__(timeout=300)
                self.message = None
                if user:
                    self.add_item(ProfileInfoSelect(current))

            @discord.ui.button(label='❌ Close', style=discord.ButtonStyle.danger, row=1)
            async def close_menu(self, interaction, button):
                self.stop()
                await interaction.response.edit_message(view=None)

            async def interaction_check(self, interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ This menu isn't yours - use `rr userinfo` to get your own.", ephemeral=True)
                    return False
                return True

            async def on_timeout(self):
                try:
                    await self.message.edit(view=None)
                except (AttributeError, discord.HTTPException):
                    pass

        view = ProfileInfoView('server')
        view.message = await ctx.send(embed=create_embed('server'), view=view)

    @commands.command(name='info', aliases=['about'])
    async def roxy_info(self, ctx):
        """Learn about Roxy"""
        bot = self.bot
        embed = discord.Embed(
            title="🤖 About Roxy Bot",
            description="Hi! I'm **Roxy**, your friendly neighborhood stats bot! I track gaming, voice calls, apps, music and messages - and help you level up!",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="📊 What I Do",
            value="• Track your gaming sessions\n• Track voice call time\n• Track time in apps (VS Code, YouTube...)\n• Monitor music listening (Spotify)\n• Monitor message counts\n• XP and leveling system\n• Server leaderboards\n• User profiles & statistics",
            inline=False
        )

        embed.add_field(name="🏠 Servers", value=len(bot.guilds), inline=True)
        embed.add_field(name="👥 Users", value=len(bot.users), inline=True)
        embed.add_field(name="🎮 Active Gamers", value=len(bot.active_sessions), inline=True)
        embed.add_field(name="🎙️ Active Calls", value=len(bot.active_voice), inline=True)
        embed.add_field(name="💻 Active Apps", value=len(bot.active_apps), inline=True)
        embed.add_field(name="🎵 Active Listeners", value=len(bot.active_listening), inline=True)

        # Patreon credits - everyone with a Supporter/Fan/VIP role in Roxy's server
        patrons = get_patrons(bot)
        if patrons:
            credits = ", ".join(f"{tier['emoji']} {member.display_name}" for member, tier in patrons)
            if len(credits) > 1000:
                credits = credits[:1000].rsplit(", ", 1)[0] + " … and more!"
            embed.add_field(name=f"💜 Patreon Supporters ({len(patrons)})", value=credits, inline=False)
        else:
            embed.add_field(name="💜 Patreon Supporters", value="Be the first! Find the Patreon button under `rr help`.", inline=False)

        if is_admin_id(ctx.author.id):
            embed.add_field(name="👑 Owner Commands", value="Use `rr help` and pick **Owner** in the dropdown", inline=False)
            embed.set_footer(text="Made with ❤️ using discord.py | You are Roxy's Owner")
        else:
            embed.set_footer(text="Made with ❤️ using discord.py | Use rr help for commands")

        if bot.user:
            embed.set_thumbnail(url=bot.user.display_avatar.url)

        view = None
        if LINK_BUTTONS:
            view = discord.ui.View()
            for label, url in LINK_BUTTONS:
                view.add_item(discord.ui.Button(label=label, url=url))
        await ctx.send(embed=embed, view=view)

    @commands.command(name='sessions')
    @commands.guild_only()
    async def active_sessions(self, ctx):
        """Who is gaming, in voice, using apps or listening right now (owner gets a Global view)"""
        bot = self.bot
        guild = ctx.guild
        state = {'global': False}

        def name_of(user_id):
            if not state['global']:
                member = guild.get_member(user_id)
                return member.display_name if member else None
            user = bot.get_user(user_id)
            return user.display_name if user else f"User {user_id}"

        def in_scope(user_id):
            return state['global'] or guild.get_member(user_id) is not None

        def section(lines, empty):
            if not lines:
                return empty
            text = ""
            for i, line in enumerate(lines):
                if len(text) + len(line) + 30 > 1024:
                    return text + f"*… and {len(lines) - i} more*"
                text += line + "\n"
            return text

        categories = {
            'all': {'label': 'All', 'emoji': '📡'},
            'gaming': {'label': 'Gaming', 'emoji': '🎮'},
            'voice': {'label': 'Voice', 'emoji': '🎙️'},
            'apps': {'label': 'Apps', 'emoji': '💻'},
            'listening': {'label': 'Listening', 'emoji': '🎵'},
        }
        PER_PAGE = 25
        state.update(category='all', page=1, pages=1)

        def session_lists():
            """Current sessions per category: key -> (title, lines, text when empty)"""
            gaming = [f"• **{name_of(uid)}** playing *{game}*" for uid, game in bot.active_sessions.items() if in_scope(uid)]
            voice = []
            for uid, call_guild_id in bot.active_voice.items():
                if state['global']:
                    call_guild = bot.get_guild(call_guild_id)
                    voice.append(f"• **{name_of(uid)}** in **{call_guild.name if call_guild else 'a server'}**")
                elif call_guild_id == guild.id:
                    voice.append(f"• **{name_of(uid)}** in a call")
            apps = [f"• **{name_of(uid)}** using *{app}*" for uid, app in bot.active_apps.items() if in_scope(uid)]
            listening = [f"• **{name_of(uid)}** listening to *{info.get('song', 'Unknown')}* by *{info.get('artist', 'Unknown')}*"
                         for uid, info in bot.active_listening.items() if in_scope(uid)]
            return {
                'gaming': ("🎮 Gaming", gaming, "No one is gaming right now"),
                'voice': ("🎙️ Voice", voice, "No one is in a voice call right now"),
                'apps': ("💻 Apps", apps, "No one is using an app right now"),
                'listening': ("🎵 Listening", listening, "No one is listening to music right now"),
            }

        def create_embed():
            scope = "🌍 All servers" if state['global'] else f"🏠 {guild.name}"
            lists = session_lists()

            if state['category'] == 'all':
                # Overview: every category, shortened to fit
                state['pages'] = 1
                embed = discord.Embed(title="📡 Active Sessions", description=f"Happening right now • {scope}", color=discord.Color.blue())
                for title, lines, empty in lists.values():
                    embed.add_field(name=f"{title} ({len(lines)})", value=section(lines, empty), inline=False)
                embed.set_footer(text="Pick a category in the dropdown to see everyone, 25 per page")
                return embed

            # One category: 25 people per page
            title, lines, empty = lists[state['category']]
            state['pages'] = max(1, (len(lines) + PER_PAGE - 1) // PER_PAGE)
            state['page'] = min(max(state['page'], 1), state['pages'])
            start = (state['page'] - 1) * PER_PAGE
            page_lines = lines[start:start + PER_PAGE]
            body = "\n".join(page_lines) if page_lines else empty
            embed = discord.Embed(
                title=f"{title} ({len(lines)})",
                description=f"Happening right now • {scope}\n\n{body}"[:4096],
                color=discord.Color.blue()
            )
            if lines:
                embed.set_footer(text=f"Page {state['page']}/{state['pages']} • Showing {start + 1}-{start + len(page_lines)} of {len(lines)}")
            return embed

        is_owner = is_admin_id(ctx.author.id)

        class SessionsSelect(discord.ui.Select):
            def __init__(self):
                options = [discord.SelectOption(label=info['label'], emoji=info['emoji'], value=key, default=(key == state['category']))
                           for key, info in categories.items()]
                super().__init__(placeholder="📡 Choose sessions to show...", options=options, row=0)

            async def callback(self, interaction):
                state['category'] = self.values[0]
                state['page'] = 1
                await self.view.refresh(interaction)

        class SessionsView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.message = None
                self.add_item(SessionsSelect())

                # Page buttons only for a single category with more than one page
                if state['category'] != 'all' and state['pages'] > 1:
                    self.previous_page.disabled = state['page'] <= 1
                    self.next_page.disabled = state['page'] >= state['pages']
                else:
                    self.remove_item(self.previous_page)
                    self.remove_item(self.next_page)

                # Only the owner gets the Global button - everyone else sees just their own server
                if is_owner:
                    self.toggle_scope.label = "🏠 Server" if state['global'] else "🌍 Global"
                else:
                    self.remove_item(self.toggle_scope)

            async def refresh(self, interaction):
                embed = create_embed()  # Recalculates the page count before the buttons are built
                new_view = SessionsView()
                new_view.message = interaction.message
                self.stop()
                await interaction.response.edit_message(embed=embed, view=new_view)

            async def interaction_check(self, interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ This menu isn't yours - use `rr sessions` to get your own.", ephemeral=True)
                    return False
                return True

            @discord.ui.button(label='◀️ Previous', style=discord.ButtonStyle.secondary, row=1)
            async def previous_page(self, interaction, button):
                state['page'] -= 1
                await self.refresh(interaction)

            @discord.ui.button(label='▶️ Next', style=discord.ButtonStyle.secondary, row=1)
            async def next_page(self, interaction, button):
                state['page'] += 1
                await self.refresh(interaction)

            @discord.ui.button(label='🌍 Global', style=discord.ButtonStyle.primary, row=1)
            async def toggle_scope(self, interaction, button):
                state['global'] = not state['global']
                state['page'] = 1
                await self.refresh(interaction)

            @discord.ui.button(label='❌ Close', style=discord.ButtonStyle.danger, row=1)
            async def close_menu(self, interaction, button):
                self.stop()
                await interaction.response.edit_message(view=None)

            async def on_timeout(self):
                try:
                    await self.message.edit(view=None)
                except (AttributeError, discord.HTTPException):
                    pass

        embed = create_embed()
        view = SessionsView()
        view.message = await ctx.send(embed=embed, view=view)

    @commands.command(name='apps', aliases=['app'])
    async def user_apps(self, ctx, member: discord.Member = None):
        """Time spent in non-game apps (VS Code, YouTube, Netflix, ...) - kept separate from gaming"""
        member = member or ctx.author
        await ctx.send(embed=await self.build_apps_embed(member))

    async def build_apps_embed(self, member):
        """App time embed - used by rr apps and the Apps view of rr profile"""
        stats = await self.db.get_app_stats(member.id)

        embed = discord.Embed(title=f"💻 {member.display_name}'s Apps", color=discord.Color.teal())
        embed.set_thumbnail(url=member.display_avatar.url)

        current_app = self.bot.active_apps.get(member.id)
        embed.add_field(
            name="📊 **App Stats**",
            value=f"🕐 **Total time:** {format_duration(stats['total_seconds'])}\n🔁 **Sessions:** {stats['sessions']:,}"
                  + (f"\n🟢 **Using now:** {current_app}" if current_app else ""),
            inline=False
        )

        if stats['favorites']:
            favorites = "\n".join(f"**{i}.** {name} - {format_duration(total)} ({count} sessions)"
                                  for i, (name, total, count) in enumerate(stats['favorites'], 1))
            embed.add_field(name="⭐ **Most Used Apps**", value=self.fit_field(favorites), inline=False)

        if stats['recent']:
            recent = "\n".join(f"• **{name}** - {format_duration(duration)} (<t:{int(ended.timestamp())}:R>)"
                               for name, ended, duration in stats['recent'])
            embed.add_field(name="📈 **Latest Sessions**", value=self.fit_field(recent), inline=False)

        if not stats['sessions'] and not current_app:
            embed.description = "No app time yet. Apps like VS Code, YouTube and Netflix show up here when Discord shows them as your activity."

        embed.set_footer(text="💜 App time is tracked separately from gaming • earns 1 XP per minute")
        return embed

    def fit_field(self, text, limit=1024):
        """Fit a list field into Discord's limit by shortening names (bold titles, italic artists,
        albums) just enough - every entry stays visible. Hiding entries is only a last resort."""
        if len(text) <= limit:
            return text

        def shorten(name, max_len):
            return name if len(name) <= max_len else name[:max_len - 1].rstrip() + "…"

        for max_len in range(60, 5, -2):
            fitted = re.sub(r'\*\*(.+?)\*\*', lambda m: f"**{shorten(m.group(1), max_len)}**", text)
            fitted = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', lambda m: f"*{shorten(m.group(1), max_len)}*", fitted)
            # Album names in the listening history: "*Artist* (Album) - "
            fitted = re.sub(r'(\*[^*\n]+\* \()([^)\n]+)(\) - )', lambda m: m.group(1) + shorten(m.group(2), max_len) + m.group(3), fitted)
            if len(fitted) <= limit:
                return fitted

        # Still too long even with short names - cut at a whole line
        suffix = "\n*…more entries hidden (names too long)*"
        kept = ""
        for line in text.split("\n"):
            if len(kept) + len(line) + 1 + len(suffix) > limit:
                break
            kept += line + "\n"
        return (kept.rstrip("\n") + suffix)[:limit]

    def get_xp_for_level(self, level):
        """Calculate total XP needed to reach a specific level"""
        if level <= 1:
            return 0
        # Progressive XP: Level N needs (N-1) * N * 50 total XP
        # Level 2: 100 XP, Level 3: 300 XP, Level 4: 600 XP, etc.
        return (level - 1) * level * 50
    
    def calculate_level_from_xp(self, xp):
        """Calculate level from total XP using progressive system"""
        level = 1
        while self.get_xp_for_level(level + 1) <= xp:
            level += 1
        return level
    
    def get_level_emoji(self, level, is_admin=False):
        """Get appropriate emoji for level"""
        if is_admin:
            return "👑"  # Crown for admin always
        elif level >= 50:
            return "💎"
        elif level >= 30:
            return "🌟"
        elif level >= 20:
            return "⭐"
        elif level >= 10:
            return "✨"
        elif level >= 5:
            return "🔥"
        else:
            return "🌱"
    
    def get_rank_title(self, level):
        """Get rank title based on level"""
        if level >= 50:
            return "Legend"
        elif level >= 30:
            return "Master"
        elif level >= 20:
            return "Expert"
        elif level >= 10:
            return "Veteran"
        elif level >= 5:
            return "Regular"
        else:
            return "Newcomer"
    
    def get_gaming_rank(self, hours):
        """Get gaming rank based on hours played"""
        if hours >= 100:
            return "Gaming Legend 👑"
        elif hours >= 50:
            return "Hardcore Gamer 💎"
        elif hours >= 20:
            return "Dedicated Player 🌟"
        elif hours >= 10:
            return "Active Gamer ⭐"
        elif hours >= 5:
            return "Casual Player ✨"
        else:
            return "New Gamer 🌱"
    
    def get_music_rank(self, hours):
        """Get music rank based on hours listened"""
        if hours >= 500:
            return "Music Virtuoso 🎼"
        elif hours >= 200:
            return "Music Master 🎵"
        elif hours >= 100:
            return "Music Enthusiast 🎶"
        elif hours >= 50:
            return "Dedicated Listener 🎧"
        elif hours >= 20:
            return "Active Listener 🎤"
        elif hours >= 10:
            return "Music Fan 🎸"
        elif hours >= 5:
            return "Getting Started 🎹"
        else:
            return "New Listener 🎺"
    
    def get_voice_achievement(self, hours):
        """Highest voice call milestone reached"""
        for threshold, name in ((500, "📡 Voice Legend (500+ hours)"), (100, "🗣️ Voice Veteran (100+ hours)"),
                                (50, "🎧 Voice Regular (50+ hours)"), (10, "📞 Chatty Caller (10+ hours)"),
                                (1, "🎙️ First Call (1+ hour)")):
            if hours >= threshold:
                return name
        return None

    def get_app_achievement(self, hours):
        """Highest app usage milestone reached"""
        for threshold, name in ((500, "🧠 Digital Legend (500+ hours)"), (100, "🚀 App Master (100+ hours)"),
                                (50, "🖥️ Productivity Pro (50+ hours)"), (10, "⌨️ Power User (10+ hours)"),
                                (1, "💻 App Explorer (1+ hour)")):
            if hours >= threshold:
                return name
        return None

    def get_achievements(self, level, messages, gaming_hours, listening_hours, is_admin=False, voice_hours=0, app_hours=0):
        """Get recent achievements to display"""
        achievements = []
        extra = [a for a in (self.get_voice_achievement(voice_hours), self.get_app_achievement(app_hours)) if a]

        # Admin-specific achievements
        if is_admin:
            achievements.append("👑 Roxy Bot Owner")
            return "\n".join([f"• {achievement}" for achievement in achievements + extra])
        
        # Level-based achievements
        if level >= 20:
            achievements.append("💎 Master Level (20+)")
        elif level >= 10:
            achievements.append("🏆 Reached Level 10+")
        elif level >= 5:
            achievements.append("⭐ Active Member")
        
        # Message-based achievements
        if messages >= 1000:
            achievements.append("💬 Chatterbox (1000+ messages)")
        elif messages >= 500:
            achievements.append("🗣️ Conversationalist")
        elif messages >= 100:
            achievements.append("📝 Regular Chatter")
        
        # Gaming achievements
        if gaming_hours >= 50:
            achievements.append("🎮 Gaming Master (50+ hours)")
        elif gaming_hours >= 20:
            achievements.append("🕹️ Dedicated Gamer")
        elif gaming_hours >= 10:
            achievements.append("🎯 Gaming Enthusiast")
        
        # Music achievements
        if listening_hours >= 100:
            achievements.append("🎵 Music Enthusiast (100+ hours)")
        elif listening_hours >= 50:
            achievements.append("🎧 Dedicated Listener")
        elif listening_hours >= 20:
            achievements.append("🎤 Active Listener")
        
        achievements += extra

        # Return max 5 achievements for non-admins
        return "\n".join([f"• {achievement}" for achievement in achievements[:5]]) if achievements else None
    
    def get_gaming_achievements(self, hours, total_sessions, longest_session_minutes, is_admin=False):
        """Get gaming-specific achievements"""
        achievements = []
        
        # Admin gets special gaming achievements
        if is_admin:
            achievements.append("👑 Gaming Owner")
            if hours >= 10:
                achievements.append("🔱 Elite Gaming Authority")
            return "\n".join([f"• {achievement}" for achievement in achievements])
        
        # Playtime achievements
        if hours >= 100:
            achievements.append("🏆 Century Gamer (100+ hours)")
        elif hours >= 50:
            achievements.append("💎 Gaming Master (50+ hours)")
        elif hours >= 20:
            achievements.append("🌟 Dedicated Player (20+ hours)")
        elif hours >= 10:
            achievements.append("⭐ Active Gamer (10+ hours)")
        elif hours >= 5:
            achievements.append("✨ Casual Player (5+ hours)")
        
        # Session achievements
        if total_sessions >= 100:
            achievements.append("🎲 Session Master (100+ sessions)")
        elif total_sessions >= 50:
            achievements.append("🎯 Session Expert (50+ sessions)")
        elif total_sessions >= 20:
            achievements.append("🎮 Regular Gamer (20+ sessions)")
        
        # Longest session achievements
        if longest_session_minutes >= 300:  # 5+ hours
            achievements.append("⏰ Marathon Gamer (5+ hour session)")
        elif longest_session_minutes >= 180:  # 3+ hours
            achievements.append("🕐 Extended Session (3+ hours)")
        elif longest_session_minutes >= 120:  # 2+ hours
            achievements.append("⏱️ Long Session (2+ hours)")
        
        # Return max 3 achievements
        return "\n".join([f"• {achievement}" for achievement in achievements[:3]]) if achievements else None
    
    def get_music_achievements(self, hours, total_sessions, longest_session_minutes, is_admin=False):
        """Get music-specific achievements"""
        achievements = []
        
        # Admin gets special music achievements
        if is_admin:
            achievements.append("👑 Music Owner")
            if hours >= 10:
                achievements.append("🔱 Elite Music Authority")
            return "\n".join([f"• {achievement}" for achievement in achievements])
        
        # Listening time achievements
        if hours >= 500:
            achievements.append("🎼 Music Virtuoso (500+ hours)")
        elif hours >= 200:
            achievements.append("🎵 Music Master (200+ hours)")
        elif hours >= 100:
            achievements.append("🎶 Music Enthusiast (100+ hours)")
        elif hours >= 50:
            achievements.append("🎧 Dedicated Listener (50+ hours)")
        elif hours >= 20:
            achievements.append("🎤 Active Listener (20+ hours)")
        elif hours >= 10:
            achievements.append("🎸 Music Fan (10+ hours)")
        elif hours >= 5:
            achievements.append("🎹 Getting Started (5+ hours)")
        
        # Session achievements
        if total_sessions >= 1000:
            achievements.append("🏆 Session Legend (1000+ sessions)")
        elif total_sessions >= 500:
            achievements.append("💎 Session Master (500+ sessions)")
        elif total_sessions >= 100:
            achievements.append("🌟 Session Expert (100+ sessions)")
        elif total_sessions >= 50:
            achievements.append("⭐ Regular Listener (50+ sessions)")
        
        # Marathon listening achievements
        if longest_session_minutes >= 480:  # 8+ hours
            achievements.append("🏃‍♀️ Marathon Listener (8+ hour session)")
        elif longest_session_minutes >= 360:  # 6+ hours
            achievements.append("⏰ Extended Listening (6+ hours)")
        elif longest_session_minutes >= 180:  # 3+ hours
            achievements.append("🕐 Long Session (3+ hours)")
        elif longest_session_minutes >= 120:  # 2+ hours
            achievements.append("⏱️ Focused Listening (2+ hours)")
        
        # Return max 3 achievements
        return "\n".join([f"• {achievement}" for achievement in achievements[:3]]) if achievements else None

async def setup(bot):
    await bot.add_cog(RoxyStats(bot))
    print("📊 Roxy's Stats cog loaded!")