import discord
from discord.ext import commands
from database import RoxyDatabase
from config import is_admin_id
from datetime import datetime, timedelta
import asyncio

class RoxyStats(commands.Cog):
    """Roxy's statistics and analytics system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = RoxyDatabase()
    
    @commands.command(name='profile', aliases=['p', 'stats'])
    async def user_profile(self, ctx, member: discord.Member = None):
        """Display comprehensive user profile with navigation"""
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
                    name="🔱 ROXY BOT ADMINISTRATOR 🔱",
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
                level_title = f"👑 **Level {level}** (Administrator)"
            else:
                level_title = f"{level_emoji} **Level {level}**"
            
            embed.add_field(
                name=level_title,
                value=f"**Progress:** {progress_xp}/{next_level_xp - current_level_xp} ({progress_percentage}%)\n**Total XP:** {xp:,}/{next_level_xp:,}",
                inline=False
            )
            
            # === ACTIVITY STATS SECTION ===
            if is_admin:
                rank_title = "🔱 Bot Administrator"
            else:
                rank_title = self.get_rank_title(level)
                
            activity_stats = f"""
            📝 **{total_messages:,}** Messages
            🎮 **{hours}h {minutes}m** Gaming
            🎵 **{listening_hours}h {listening_minutes}m** Listening
            🎯 **{rank_title}**
            """
            
            embed.add_field(
                name="📊 **Activity Overview**",
                value=activity_stats.strip(),
                inline=True
            )
            
            # === CURRENT STATUS SECTION ===
            status_lines = []
            
            if current_game:
                status_lines.append(f"🎮 Playing **{current_game}**")
            
            if current_song and current_artist:
                status_lines.append(f"🎵 Listening to **{current_song}** by **{current_artist}**")
            
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
                inline=True
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
            achievements = self.get_achievements(level, total_messages, hours, listening_hours, is_admin)
            if achievements:
                embed.add_field(
                    name="🏆 **Recent Achievements**",
                    value=achievements,
                    inline=False
                )

            # Achievements granted by the admin with !r ach give
            special_achievements = await self.db.get_user_custom_achievements(member.id)
            if special_achievements:
                embed.add_field(
                    name="🎖️ **Special Achievements**",
                    value="\n".join(f"• {name}" for name, _ in special_achievements)[:1024],
                    inline=False
                )

            # === FOOTER ===
            if is_admin:
                embed.set_footer(
                    text=f"👑 Roxy Bot Administrator • Ultimate Authority",
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
                    title=f"👑 {member.display_name}'s Level (Administrator)",
                    color=0xffd700
                )
            else:
                embed = discord.Embed(
                    title=f"{level_emoji} {member.display_name}'s Level",
                    color=0xf1c40f
                )
            
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            embed.add_field(
                name="📊 **Current Progress**",
                value=f"**Level:** {level}\n**Progress:** {progress_percentage}%\n**Total XP:** {xp:,} / {next_level_xp:,}",
                inline=False
            )
            
            # Show XP sources breakdown
            message_xp = total_messages * 5
            gaming_xp = total_playtime // 60
            listening_xp = total_listening_time // 120
            
            embed.add_field(
                name="✨ **XP Sources**",
                value=f"💬 **Messages:** {message_xp:,} XP ({total_messages:,} messages)\n🎮 **Gaming:** {gaming_xp:,} XP ({total_playtime//3600}h {(total_playtime%3600)//60}m)\n🎵 **Listening:** {listening_xp:,} XP ({total_listening_time//3600}h {(total_listening_time%3600)//60}m)",
                inline=False
            )
            
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
                embed.set_footer(text="👑 Keep being an awesome administrator! • Use dropdown to switch views")
            else:
                embed.set_footer(text="💜 Keep chatting, gaming, and listening to level up! • Use dropdown to switch views")
            
            return embed
        
        async def create_music_embed():
            """Create music listening overview embed"""
            
            listening_hours = total_listening_time // 3600
            listening_minutes = (total_listening_time % 3600) // 60
            
            if is_admin:
                embed = discord.Embed(
                    title=f"👑 {member.display_name}'s Music (Administrator)",
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
                    history_text += f"• **{song_title}** by *{artist_name}* - {music_minutes}m {music_seconds}s ({time_ago})\n"
                
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
                    title=f"👑 {member.display_name}'s Gaming (Administrator)",
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
                    history_text += f"• **{game}** - {game_minutes}m {game_seconds}s ({time_ago})\n"
                
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
                    title=f"👑 {member.display_name}'s Complete Game List (Administrator)",
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
                value=games_text.strip(),
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
                    title=f"👑 {member.display_name}'s Gaming History (Administrator)",
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
                history_text += f"• **{game}** - {game_minutes}m {game_seconds}s ({time_ago})\n"
            
            embed.add_field(
                name=f"Recent Gaming Sessions (Page {page}/{total_pages})",
                value=history_text.strip(),
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
                    title=f"👑 {member.display_name}'s Complete Artist List (Administrator)",
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
                value=artists_text.strip(),
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
                    title=f"👑 {member.display_name}'s Complete Song List (Administrator)",
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
                value=songs_text.strip(),
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
                    title=f"👑 {member.display_name}'s Listening History (Administrator)",
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
                history_text += f"• **{song_title}** by *{artist_name}*{album_text} - {music_minutes}m {music_seconds}s ({time_ago})\n"
            
            embed.add_field(
                name=f"Recent Listening Sessions (Page {page}/{total_pages})",
                value=history_text.strip(),
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
    async def leaderboard(self, ctx, category='messages'):
        """Roxy's server leaderboards"""
        valid_categories = ['messages', 'playtime', 'listening', 'level', 'xp']
        
        if category not in valid_categories:
            embed = discord.Embed(
                title="❌ Invalid Category",
                description=f"**Valid categories:** {', '.join(valid_categories)}",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        leaderboard_data = await self.db.get_leaderboard(category, 10)
        
        if not leaderboard_data:
            embed = discord.Embed(
                title="❌ No leaderboard data",
                description="No data available for this category",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Create beautiful leaderboard embed
        embed = discord.Embed(
            title=f"🏆 {category.title()} Leaderboard",
            description=f"**Top performers in {ctx.guild.name}**",
            color=0xffd700  # Gold color
        )
        
        leaderboard_text = ""
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (user_id, username, display_name, value) in enumerate(leaderboard_data):
            # Get member object to check if still in server
            member = ctx.guild.get_member(user_id)
            if member and i < 10:  # Only show top 10
                name = member.display_name
                
                # Add crown for admin
                if is_admin_id(user_id):
                    name = f"👑 {name}"
                
                # Format value based on category
                if category in ['playtime', 'listening']:
                    hours = value // 3600
                    minutes = (value % 3600) // 60
                    formatted_value = f"{hours}h {minutes}m"
                elif category in ['xp', 'messages']:
                    formatted_value = f"{value:,}"
                else:
                    formatted_value = str(value)
                
                # Create beautiful ranking
                if i < 3:
                    medal = medals[i]
                    leaderboard_text += f"{medal} **{name}** • `{formatted_value}`\n"
                else:
                    leaderboard_text += f"`#{i+1:2}` **{name}** • `{formatted_value}`\n"
        
        embed.add_field(
            name="📊 **Rankings**",
            value=leaderboard_text or "No users found in this server.",
            inline=False
        )
        
        # Add category-specific footer
        category_tips = {
            'messages': '💬 Stay active in chat to climb!',
            'playtime': '🎮 Game more to reach the top!',
            'listening': '🎵 Listen to more music to climb!',
            'level': '⭐ Balance all activities!',
            'xp': '✨ Earn XP through all activities!'
        }
        
        embed.set_footer(
            text=f"💜 {category_tips.get(category, 'Keep being awesome!')}",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        await ctx.send(embed=embed)
    
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
    
    def get_achievements(self, level, messages, gaming_hours, listening_hours, is_admin=False):
        """Get recent achievements to display"""
        achievements = []
        
        # Admin-specific achievements
        if is_admin:
            achievements.append("👑 Roxy Bot Administrator")
            return "\n".join([f"• {achievement}" for achievement in achievements])
        
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
        
        # Return max 3 achievements for non-admins
        return "\n".join([f"• {achievement}" for achievement in achievements[:3]]) if achievements else None
    
    def get_gaming_achievements(self, hours, total_sessions, longest_session_minutes, is_admin=False):
        """Get gaming-specific achievements"""
        achievements = []
        
        # Admin gets special gaming achievements
        if is_admin:
            achievements.append("👑 Gaming Administrator")
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
            achievements.append("👑 Music Administrator")
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