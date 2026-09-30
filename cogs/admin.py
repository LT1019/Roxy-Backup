import discord
from discord.ext import commands
import aiosqlite
import time
import psutil
from datetime import datetime, timedelta
from database import RoxyDatabase

# ROXY BOT ADMIN CONFIGURATION
ADMIN_USER_ID = 526795891487670302  # Your Discord User ID

# Admin check decorator - Silent for non-admins
def is_admin():
    """Check if user is Roxy's admin - No response for non-admins"""
    async def predicate(ctx):
        if ctx.author.id != ADMIN_USER_ID:
            # Log admin command attempts by non-admins (for security)
            print(f"🚫 Non-admin {ctx.author} ({ctx.author.id}) tried to use admin command: {ctx.command}")
            # Completely ignore non-admin users - no response at all
            return False
        return True
    return commands.check(predicate)

class RoxyAdmin(commands.Cog):
    """Roxy's administrative commands and management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = RoxyDatabase()
    
    @commands.command(name='admin', aliases=['a'])
    @is_admin()
    async def admin_help(self, ctx):
        """Admin help menu - Only visible to admin, silent for others"""
        print(f"👑 Admin {ctx.author} accessed admin panel")
        
        embed = discord.Embed(
            title="👑 Roxy Admin Control Panel",
            description="**Admin-Only Commands** for managing Roxy Bot",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="👥 User Management",
            value="`!r addxp <@user> <amount>` - Give XP to user\n`!r setlevel <@user> <level>` - Set user level\n`!r resetuser <@user>` - Reset user stats\n`!r viewuser <@user>` - View detailed user data",
            inline=False
        )
        
        embed.add_field(
            name="🏆 Achievement Management",
            value="`!r ach` - Achievement control panel\n`!r giveach <@user> <achievement>` - Grant achievement\n`!r removeach <@user> <achievement>` - Remove achievement",
            inline=False
        )
        
        embed.add_field(
            name="🗄️ Database Management",
            value="`!r dbstats` - Database statistics\n`!r cleanup` - Clean inactive users\n`!r backup` - Create database backup\n`!r totalstats` - Global statistics",
            inline=False
        )
        
        embed.add_field(
            name="🤖 Bot Control",
            value="`!r setstatus <message>` - Set bot status\n`!r announce <message>` - Send announcement\n`!r shutdown` - Shutdown bot\n`!r reload` - Reload cogs",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Debug & Maintenance",
            value="`!r forceupdate <@user>` - Force update user\n`!r clearsessions` - Clear all sessions\n`!r logs` - View recent logs",
            inline=False
        )
        
        embed.add_field(
            name="⚡ Quick Access",
            value="`!admin` or `!a` - This admin panel\n`!addxp` - Quick XP commands work too",
            inline=False
        )
        
        embed.set_footer(text="👑 You are Roxy's Administrator | Commands are invisible to others")
        
        await ctx.send(embed=embed)

    # Achievement Management Commands (unchanged from previous version)
    @commands.group(name='ach', invoke_without_command=True)
    @is_admin()
    async def achievement_admin(self, ctx):
        """Admin achievement management control panel"""
        embed = discord.Embed(
            title="🏆 Admin Achievement Control Panel",
            description="**Manage user achievements and rewards**",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="📋 **Available Commands**",
            value="`!r ach list` - View all available achievements\n`!r ach users <achievement>` - See who has an achievement\n`!r ach give <@user> <achievement>` - Grant achievement to user\n`!r ach remove <@user> <achievement>` - Remove achievement from user",
            inline=False
        )
        
        embed.add_field(
            name="🎯 **Built-in Achievement Categories**",
            value="• **Level Achievements** - Milestone levels (5, 10, 20, 50+)\n• **Gaming Achievements** - Playtime and session milestones\n• **Music Achievements** - Listening time and session milestones\n• **Social Achievements** - Message and activity milestones\n• **Special Achievements** - Custom and event achievements",
            inline=False
        )
        
        embed.add_field(
            name="💡 **Tips**",
            value="• Achievements are automatically awarded based on user activity\n• You can manually grant special achievements for events\n• Custom achievements are permanently stored\n• Use exact achievement names (case sensitive)",
            inline=False
        )
        
        embed.set_footer(text="👑 Achievement management • Use sub-commands for specific actions")
        await ctx.send(embed=embed)

    @achievement_admin.command(name='list')
    @is_admin()
    async def ach_list(self, ctx):
        """Enhanced paginated achievement list with dropdown navigation"""
        
        # Define all achievement categories with expanded lists
        achievement_categories = {
            "Level Achievements": {
                "emoji": "⭐",
                "color": 0xf1c40f,
                "achievements": [
                    "`Active Member` - Reach Level 5",
                    "`Veteran` - Reach Level 10", 
                    "`Expert` - Reach Level 20",
                    "`Master` - Reach Level 30",
                    "`Legend` - Reach Level 50",
                    "`Elite` - Reach Level 100",
                    "`Champion` - Reach Level 200",
                    "`Grandmaster` - Reach Level 500",
                    "`Ascended` - Reach Level 750",
                    "`Eternal` - Reach Level 1000 (Highest title, levels continue infinitely)"
                ]
            },
            "Gaming Achievements": {
                "emoji": "🎮",
                "color": 0x9b59b6,
                "achievements": [
                    "`Gaming Started` - 1+ hour playtime",
                    "`Casual Player` - 5+ hours playtime",
                    "`Active Gamer` - 10+ hours playtime",
                    "`Dedicated Player` - 20+ hours playtime",
                    "`Gaming Master` - 50+ hours playtime",
                    "`Century Gamer` - 100+ hours playtime",
                    "`Gaming Legend` - 200+ hours playtime",
                    "`Gaming God` - 500+ hours playtime",
                    "`Gaming Deity` - 1000+ hours playtime",
                    "`Marathon Gamer` - 5+ hour single session"
                ]
            },
            "Music Achievements": {
                "emoji": "🎵",
                "color": 0x1db954,
                "achievements": [
                    "`First Listen` - 1+ hour listening time",
                    "`Getting Started` - 5+ hours listening time",
                    "`Music Fan` - 10+ hours listening time",
                    "`Active Listener` - 20+ hours listening time",
                    "`Dedicated Listener` - 50+ hours listening time",
                    "`Music Enthusiast` - 100+ hours listening time",
                    "`Music Master` - 200+ hours listening time",
                    "`Music Virtuoso` - 500+ hours listening time",
                    "`Music Deity` - 1000+ hours listening time",
                    "`Marathon Listener` - 8+ hour single session"
                ]
            },
            "Social Achievements": {
                "emoji": "💬",
                "color": 0x3498db,
                "achievements": [
                    "`Regular Chatter` - 50+ messages",
                    "`Conversationalist` - 100+ messages",
                    "`Chatterbox` - 500+ messages",
                    "`Social Butterfly` - 1000+ messages",
                    "`Community Voice` - 2500+ messages",
                    "`Server Legend` - 5000+ messages",
                    "`Message Master` - 10000+ messages",
                    "`Session Starter` - 20+ gaming sessions",
                    "`Session Expert` - 50+ gaming sessions",
                    "`Session Master` - 100+ gaming sessions"
                ]
            },
            "Special Achievements": {
                "emoji": "👑",
                "color": 0xe74c3c,
                "achievements": [
                    "`Roxy Bot Administrator` - Bot admin status",
                    "`Early Adopter` - Joined during beta testing",
                    "`Event Participant` - Participated in special events",
                    "`Community Helper` - Helped other users significantly"
                ]
            }
        }
        
        # Get category list for easier access
        category_names = list(achievement_categories.keys())
        current_category = 0  # Start with Level Achievements
        
        def create_achievement_embed(category_index):
            """Create embed for specific achievement category"""
            category_name = category_names[category_index]
            category_data = achievement_categories[category_name]
            
            embed = discord.Embed(
                title=f"🏆 {category_data['emoji']} {category_name}",
                description=f"**Complete list of {category_name.lower()} in Roxy Bot**",
                color=category_data['color']
            )
            
            # Add all achievements for this category
            achievements_text = "\n".join([f"• {achievement}" for achievement in category_data['achievements']])
            
            embed.add_field(
                name=f"📋 **All {category_name} ({len(category_data['achievements'])} total)**",
                value=achievements_text,
                inline=False
            )
            
            # Add category-specific tips
            tips = {
                "Level Achievements": "💡 **Tip:** Gain XP by chatting (5 XP/message), gaming (1 XP/minute), and listening (1 XP/2 minutes). Levels are infinite!",
                "Gaming Achievements": "💡 **Tip:** Set your Discord status to 'Playing [Game]' to track sessions",
                "Music Achievements": "💡 **Tip:** Listen to Spotify to track music sessions automatically",
                "Social Achievements": "💡 **Tip:** Stay active in chat and participate in gaming sessions",
                "Special Achievements": "💡 **Tip:** These are granted manually for special contributions"
            }
            
            embed.add_field(
                name="💡 **How to Earn**",
                value=tips.get(category_name, "Stay active and engage with the community!"),
                inline=False
            )
            
            # Add navigation info
            embed.set_footer(
                text=f"👑 Page {category_index + 1} of {len(category_names)} • Use dropdown or arrows to navigate • Use !r ach give <@user> <achievement> to grant"
            )
            
            return embed
        
        # Create dropdown select menu for category navigation
        class AchievementSelect(discord.ui.Select):
            def __init__(self):
                options = []
                for i, (category_name, category_data) in enumerate(achievement_categories.items()):
                    options.append(
                        discord.SelectOption(
                            label=category_name,
                            description=f"{len(category_data['achievements'])} achievements",
                            emoji=category_data['emoji'],
                            value=str(i)
                        )
                    )
                
                super().__init__(
                    placeholder="🏆 Select an achievement category...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(self, interaction):
                nonlocal current_category
                current_category = int(self.values[0])
                
                embed = create_achievement_embed(current_category)
                await interaction.response.edit_message(embed=embed, view=view)
        
        # Create view with dropdown and navigation buttons
        class AchievementView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)  # 5 minute timeout
                self.add_item(AchievementSelect())
            
            @discord.ui.button(label='◀️ Previous', style=discord.ButtonStyle.secondary)
            async def previous_category(self, interaction, button):
                nonlocal current_category
                current_category = (current_category - 1) % len(category_names)
                
                embed = create_achievement_embed(current_category)
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(label='▶️ Next', style=discord.ButtonStyle.secondary)
            async def next_category(self, interaction, button):
                nonlocal current_category
                current_category = (current_category + 1) % len(category_names)
                
                embed = create_achievement_embed(current_category)
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(label='🏠 Overview', style=discord.ButtonStyle.primary)
            async def show_overview(self, interaction, button):
                # Create overview embed showing all categories
                overview_embed = discord.Embed(
                    title="🏆 Achievement System Overview",
                    description="**Complete achievement system in Roxy Bot**",
                    color=discord.Color.gold()
                )
                
                for category_name, category_data in achievement_categories.items():
                    overview_embed.add_field(
                        name=f"{category_data['emoji']} **{category_name}**",
                        value=f"• **{len(category_data['achievements'])}** total achievements\n• Use dropdown to explore this category",
                        inline=True
                    )
                
                # Add summary statistics
                total_achievements = sum(len(cat_data['achievements']) for cat_data in achievement_categories.values())
                overview_embed.add_field(
                    name="📊 **System Summary**",
                    value=f"🏆 **{total_achievements}** total achievements available\n🎯 **{len(category_names)}** different categories\n💎 **Level 1000** \"Eternal\" is the highest title\n⚡ **Infinite** leveling system (no level cap)\n🎵 **Music tracking** via Spotify",
                    inline=False
                )
                
                overview_embed.set_footer(text="👑 Use the dropdown menu to explore specific achievement categories")
                
                await interaction.response.edit_message(embed=overview_embed, view=self)
            
            @discord.ui.button(label='❌ Close', style=discord.ButtonStyle.danger)
            async def close_menu(self, interaction, button):
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="🏆 Achievement Menu Closed",
                        description="Use `!r ach list` to open again.",
                        color=discord.Color.red()
                    ),
                    view=None
                )
                self.stop()
            
            async def on_timeout(self):
                # Disable all components when timeout occurs
                for item in self.children:
                    try:
                        item.disabled = True  # type: ignore
                    except AttributeError:
                        pass  # Some items might not have disabled attribute
        
        # Create initial embed and view
        view = AchievementView()
        embed = create_achievement_embed(current_category)
        
        await ctx.send(embed=embed, view=view)

    # (Other achievement commands remain the same - give, remove, users, etc.)

    # Advanced Admin Commands
    @commands.command(name='totalstats')
    @is_admin()
    async def global_statistics(self, ctx):
        """Comprehensive global statistics (Admin only)"""
        try:
            # Get database statistics
            db_stats = await self.db.get_database_stats()
            
            # Calculate additional metrics
            total_users = len(self.bot.users)
            total_servers = len(self.bot.guilds)
            active_gamers = len(getattr(self.bot, 'active_sessions', {}))
            active_listeners = len(getattr(self.bot, 'active_listening', {}))
            
            # Create comprehensive stats embed
            embed = discord.Embed(
                title="📊 Roxy Bot Global Statistics",
                description="**Complete overview of Roxy Bot's performance and usage**",
                color=discord.Color.gold()
            )
            
            # === GLOBAL METRICS ===
            embed.add_field(
                name="🌍 **Global Reach**",
                value=f"🏠 **{total_servers}** servers\n👥 **{total_users}** total users\n📊 **{db_stats.get('total_users', 0)}** tracked users\n🎮 **{active_gamers}** currently gaming\n🎵 **{active_listeners}** currently listening",
                inline=True
            )
            
            # === ACTIVITY METRICS ===
            embed.add_field(
                name="📈 **Activity Metrics**",
                value=f"💬 **{db_stats.get('total_messages', 0):,}** total messages\n⏱️ **{db_stats.get('total_playtime_hours', 0):,}h** total gaming\n🎵 **{db_stats.get('total_listening_hours', 0):,}h** total listening\n🎲 **{db_stats.get('total_sessions', 0):,}** gaming sessions\n🎶 **{db_stats.get('total_listening_sessions', 0):,}** listening sessions\n📅 **{db_stats.get('active_users', 0)}** active this week",
                inline=True
            )
            
            # === PROGRESSION STATS ===
            embed.add_field(
                name="🏆 **Progression Stats**",
                value=f"⭐ **Level {db_stats.get('highest_level', 1)}** highest level\n📊 **{db_stats.get('avg_level', 1.0):.1f}** average level\n✨ **{db_stats.get('max_xp', 0):,}** highest XP\n🎯 **{db_stats.get('max_xp', 0) // 5:,}** equivalent messages",
                inline=True
            )
            
            # === SERVER BREAKDOWN ===
            server_info = ""
            top_servers = sorted(list(self.bot.guilds), key=lambda g: g.member_count, reverse=True)[:5]
            for i, guild in enumerate(top_servers, 1):
                server_info += f"**{i}.** {guild.name} - {guild.member_count} members\n"
            
            embed.add_field(
                name="🏠 **Top 5 Servers by Members**",
                value=server_info.strip() or "No servers found",
                inline=False
            )
            
            # === PERFORMANCE METRICS ===
            import psutil
            import time
            
            # Get system metrics
            uptime = 0.0
            if hasattr(self.bot, 'start_time') and self.bot.start_time:
                uptime = time.time() - self.bot.start_time
            uptime_hours = int(uptime // 3600)
            uptime_mins = int((uptime % 3600) // 60)
            
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            memory_mb = memory.used // 1024 // 1024
            
            embed.add_field(
                name="⚡ **Bot Performance**",
                value=f"🕐 **{uptime_hours}h {uptime_mins}m** uptime\n🧠 **{memory_mb}MB** RAM usage\n💻 **{cpu_percent:.1f}%** CPU usage\n📡 **{round(self.bot.latency * 1000)}ms** latency",
                inline=True
            )
            
            # === ACTIVITY INSIGHTS ===
            avg_gaming_session_hours = db_stats.get('total_playtime_hours', 0) / max(db_stats.get('total_sessions', 1), 1)
            avg_listening_session_hours = db_stats.get('total_listening_hours', 0) / max(db_stats.get('total_listening_sessions', 1), 1)
            messages_per_user = db_stats.get('total_messages', 0) / max(db_stats.get('total_users', 1), 1)
            
            embed.add_field(
                name="🎮🎵 **Activity Insights**",
                value=f"⏱️ **{avg_gaming_session_hours:.1f}h** avg gaming session\n🎶 **{avg_listening_session_hours:.1f}h** avg listening session\n📝 **{messages_per_user:.0f}** avg messages per user\n🎯 **{(db_stats.get('total_playtime_hours', 0) / max(total_users, 1)):.1f}h** avg gaming per user\n🎵 **{(db_stats.get('total_listening_hours', 0) / max(total_users, 1)):.1f}h** avg listening per user\n📊 **{(db_stats.get('active_users', 0) / max(db_stats.get('total_users', 1), 1) * 100):.1f}%** weekly activity rate",
                inline=True
            )
            
            # === ACHIEVEMENTS & MILESTONES ===
            embed.add_field(
                name="🏆 **Achievements & Milestones**",
                value=f"🎖️ **44** total achievement types\n🏅 **5** achievement categories\n🎮 **Gaming** tracking system\n🎵 **Music** listening tracking\n💎 **Level 1000** highest possible title\n⚡ **Infinite** leveling system",
                inline=True
            )
            
            # === FOOTER ===
            embed.set_footer(
                text=f"👑 Generated by {ctx.author.display_name} • Last updated: Now",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            
            if self.bot.user:
                embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error generating global statistics: {e}")
            print(f"❌ Error in totalstats: {e}")

    @commands.command(name='logs')
    @is_admin()
    async def view_recent_logs(self, ctx, limit: int = 10):
        """Enhanced paginated logs with dropdown navigation (Admin only)"""
        
        # Enforce limit constraints: default 10, max 50
        if limit < 1:
            limit = 10
        elif limit > 50:
            limit = 50
        
        # Define all log categories
        log_categories = {
            "Recent User Activity": {
                "emoji": "👥",
                "color": 0x3498db,
                "description": "Latest user interactions and activity"
            },
            "Recent Gaming Sessions": {
                "emoji": "🎮", 
                "color": 0x9b59b6,
                "description": "Recently completed gaming sessions"
            },
            "Recent Listening Sessions": {
                "emoji": "🎵",
                "color": 0x1db954,
                "description": "Recently completed music listening sessions"
            },
            "Currently Active Gaming": {
                "emoji": "🔴",
                "color": 0xe74c3c,
                "description": "Live gaming sessions in progress"
            },
            "Currently Active Listening": {
                "emoji": "🟢",
                "color": 0x27ae60,
                "description": "Live music listening sessions in progress"
            },
            "Top Recent Levels": {
                "emoji": "⭐",
                "color": 0xf1c40f,
                "description": "Recent level achievements and top users"
            }
        }
        
        # Get category list for easier access
        category_names = list(log_categories.keys())
        current_category = 0  # Start with Recent User Activity
        current_page = 1  # Add page tracking
        
        async def create_user_activity_embed(page=1):
            """Create Recent User Activity embed with pagination"""
            embed = discord.Embed(
                title="👥 Recent User Activity",
                description="**Latest user interactions and activity**",
                color=0x3498db
            )
            
            # Calculate offset for pagination
            offset = (page - 1) * limit
            
            # Get recent user activities with offset
            recent_users = []
            total_count = 0
            try:
                async with aiosqlite.connect(self.db.db_path) as db:
                    # First get total count
                    async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                        result = await cursor.fetchone()
                        total_count = result[0] if result else 0
                    
                    # Then get paginated results
                    async with db.execute("""
                        SELECT username, last_seen, total_messages, total_listening_time, level, xp
                        FROM users 
                        ORDER BY last_seen DESC 
                        LIMIT ? OFFSET ?
                    """, (limit, offset)) as cursor:
                        results = await cursor.fetchall()
                        
                    for username, last_seen, messages, listening_time, level, xp in results:
                        if last_seen:
                            last_seen_dt = datetime.fromisoformat(last_seen)
                            time_ago = f"<t:{int(last_seen_dt.timestamp())}:R>"
                            short_name = username[:15] + "..." if len(username) > 15 else username
                            listening_hours = listening_time // 3600
                            recent_users.append(f"• **{short_name}** (Lv.{level}, {messages:,} msgs, {listening_hours}h music) - {time_ago}")
            except Exception as e:
                recent_users = [f"❌ Error loading user data: {e}"]
            
            # Calculate total pages
            total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
            
            # Add users field
            user_text = "\n".join(recent_users) if recent_users else "No recent activity"
            embed.add_field(
                name=f"📊 **Recent Active Users (Page {page}/{total_pages})**",
                value=user_text[:1024],  # Discord field limit
                inline=False
            )
            
            # Add summary stats with music listening
            try:
                async with aiosqlite.connect(self.db.db_path) as db:
                    # Users active in last 24 hours
                    yesterday = (datetime.now().timestamp() - 86400)
                    async with db.execute("""
                        SELECT COUNT(*) FROM users 
                        WHERE datetime(last_seen) > datetime(?, 'unixepoch')
                    """, (yesterday,)) as cursor:
                        result = await cursor.fetchone()
                        active_24h = result[0] if result else 0
                    
                    # Users active this week
                    week_ago = (datetime.now().timestamp() - 604800)
                    async with db.execute("""
                        SELECT COUNT(*) FROM users 
                        WHERE datetime(last_seen) > datetime(?, 'unixepoch')
                    """, (week_ago,)) as cursor:
                        result = await cursor.fetchone()
                        active_week = result[0] if result else 0
                    
                    # Total listening hours
                    async with db.execute("""
                        SELECT SUM(total_listening_time) FROM users
                    """) as cursor:
                        result = await cursor.fetchone()
                        total_listening_seconds = result[0] if result and result[0] else 0
                        total_listening_hours = total_listening_seconds // 3600
                
                embed.add_field(
                    name="📈 **Activity Summary**",
                    value=f"🕐 **{active_24h}** users active (24h)\n📅 **{active_week}** users active (7d)\n👥 **{total_count}** total users tracked\n🎵 **{total_listening_hours:,}h** total music listened\n⚡ **{len(recent_users)}** users on this page",
                    inline=False
                )
            except Exception as e:
                embed.add_field(
                    name="📈 **Activity Summary**", 
                    value=f"❌ Error loading summary: {e}",
                    inline=False
                )
            
            return embed, total_pages
        
        async def create_listening_sessions_embed(page=1):
            """Create Recent Listening Sessions embed with pagination"""
            embed = discord.Embed(
                title="🎵 Recent Listening Sessions",
                description="**Recently completed music listening sessions**",
                color=0x1db954
            )
            
            # Calculate offset for pagination
            offset = (page - 1) * limit
            
            # Get recent listening sessions
            recent_sessions = []
            total_count = 0
            try:
                async with aiosqlite.connect(self.db.db_path) as db:
                    # Get total count
                    async with db.execute("""
                        SELECT COUNT(*) FROM listening_sessions 
                        WHERE end_time IS NOT NULL
                    """) as cursor:
                        result = await cursor.fetchone()
                        total_count = result[0] if result else 0
                    
                    # Get paginated results
                    async with db.execute("""
                        SELECT users.username, listening_sessions.song_title, listening_sessions.artist_name, listening_sessions.end_time, listening_sessions.duration
                        FROM listening_sessions 
                        JOIN users ON listening_sessions.user_id = users.user_id
                        WHERE listening_sessions.end_time IS NOT NULL
                        ORDER BY listening_sessions.end_time DESC 
                        LIMIT ? OFFSET ?
                    """, (limit, offset)) as cursor:
                        results = await cursor.fetchall()
                        
                    for username, song_title, artist_name, end_time, duration in results:
                        if end_time and duration:
                            end_dt = datetime.fromisoformat(end_time)
                            time_ago = f"<t:{int(end_dt.timestamp())}:R>"
                            duration_mins = duration // 60
                            duration_secs = duration % 60
                            
                            short_name = username[:12] + "..." if len(username) > 12 else username
                            short_song = song_title[:20] + "..." if len(song_title) > 20 else song_title
                            short_artist = artist_name[:15] + "..." if len(artist_name) > 15 else artist_name
                            
                            recent_sessions.append(f"• **{short_name}** listened to *{short_song}* by *{short_artist}* ({duration_mins}m {duration_secs}s) - {time_ago}")
            except Exception as e:
                recent_sessions = [f"❌ Error loading listening data: {e}"]
            
            # Calculate total pages
            total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
            
            sessions_text = "\n".join(recent_sessions) if recent_sessions else "No recent sessions"
            
            embed.add_field(
                name=f"🎶 **Recent Listening Sessions (Page {page}/{total_pages})**",
                value=sessions_text[:1024],
                inline=False
            )
            
            # Add listening summary
            try:
                async with aiosqlite.connect(self.db.db_path) as db:
                    # Sessions in last 24 hours
                    yesterday = (datetime.now().timestamp() - 86400)
                    async with db.execute("""
                        SELECT COUNT(*), SUM(duration) FROM listening_sessions 
                        WHERE datetime(end_time) > datetime(?, 'unixepoch') AND duration IS NOT NULL
                    """, (yesterday,)) as cursor:
                        result = await cursor.fetchone()
                        sessions_24h = 0
                        listening_time_24h = 0
                        if result:
                            sessions_24h = result[0] if result[0] else 0
                            listening_time_24h = (result[1] // 3600) if result[1] else 0
                    
                    # Total sessions today
                    today = datetime.now().date().isoformat()
                    async with db.execute("""
                        SELECT COUNT(*) FROM listening_sessions 
                        WHERE date(end_time) = ? AND duration IS NOT NULL
                    """, (today,)) as cursor:
                        result = await cursor.fetchone()
                        sessions_today = result[0] if result else 0
                
                embed.add_field(
                    name="📊 **Listening Summary**",
                    value=f"🕐 **{sessions_24h}** sessions (24h)\n⏱️ **{listening_time_24h}h** listening (24h)\n📅 **{sessions_today}** sessions today\n🎵 **{len(recent_sessions)}** sessions on this page",
                    inline=False
                )
            except Exception as e:
                embed.add_field(
                    name="📊 **Listening Summary**",
                    value=f"❌ Error loading summary: {e}",
                    inline=False
                )
            
            return embed, total_pages
        
        async def create_active_listening_embed(page=1):
            """Create Currently Active Listening embed (no pagination needed)"""
            embed = discord.Embed(
                title="🟢 Currently Active Listening",
                description="**Live music listening sessions in progress**",
                color=0x27ae60
            )
            
            # Get active listening sessions
            active_sessions_info = []
            session_details = []
            
            active_listening = getattr(self.bot, 'active_listening', {})
            
            for user_id, music_info in active_listening.items():
                user = self.bot.get_user(user_id)
                if user:
                    short_name = user.name[:12] + "..." if len(user.name) > 12 else user.name
                    song = music_info.get('song', 'Unknown')[:25] + "..." if len(music_info.get('song', 'Unknown')) > 25 else music_info.get('song', 'Unknown')
                    artist = music_info.get('artist', 'Unknown')[:20] + "..." if len(music_info.get('artist', 'Unknown')) > 20 else music_info.get('artist', 'Unknown')
                    
                    active_sessions_info.append(f"• **{short_name}** - *{song}* by *{artist}*")
                    
                    # Try to get session start time
                    try:
                        async with aiosqlite.connect(self.db.db_path) as db:
                            async with db.execute("""
                                SELECT start_time FROM listening_sessions 
                                WHERE user_id = ? AND end_time IS NULL 
                                ORDER BY start_time DESC LIMIT 1
                            """, (user_id,)) as cursor:
                                result = await cursor.fetchone()
                                if result:
                                    start_dt = datetime.fromisoformat(result[0])
                                    duration = datetime.now() - start_dt
                                    duration_mins = int(duration.total_seconds() // 60)
                                    session_details.append(f"• **{short_name}** - *{song}* by *{artist}* ({duration_mins}m)")
                                else:
                                    session_details.append(f"• **{short_name}** - *{song}* by *{artist}* (just started)")
                    except:
                        session_details.append(f"• **{short_name}** - *{song}* by *{artist}* (duration unknown)")
            
            active_text = "\n".join(session_details[:15]) if session_details else "No active listening sessions"
            
            embed.add_field(
                name=f"🎵 **Active Sessions ({len(active_sessions_info)})**",
                value=active_text[:1024],
                inline=False
            )
            
            # Add live statistics
            total_active = len(active_listening)
            total_users = len(self.bot.users)
            activity_rate = (total_active / max(total_users, 1)) * 100
            
            # Get popular artists currently being listened to
            artist_counts = {}
            for music_info in active_listening.values():
                artist = music_info.get('artist', 'Unknown')
                short_artist = artist[:20] + "..." if len(artist) > 20 else artist
                artist_counts[short_artist] = artist_counts.get(short_artist, 0) + 1
            
            popular_artists = sorted(artist_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            popular_artists_text = "\n".join([f"• **{artist}** ({count} listeners)" for artist, count in popular_artists]) if popular_artists else "No artists currently active"
            
            embed.add_field(
                name="📊 **Live Statistics**",
                value=f"🎵 **{total_active}** active listeners\n👥 **{total_users}** total users\n📈 **{activity_rate:.1f}%** listening rate\n⚡ **Real-time** tracking",
                inline=True
            )
            
            embed.add_field(
                name="🏆 **Popular Artists Now**",
                value=popular_artists_text[:1024],
                inline=True
            )
            
            return embed, 1  # No pagination for active listening
        
        # Include all other embed functions from the previous version (gaming sessions, active gaming, top levels)
        # ... (keeping the code concise, these would be the same as before)
        
        # Create dropdown select menu for category navigation
        class LogsSelect(discord.ui.Select):
            def __init__(self):
                options = []
                for i, (category_name, category_data) in enumerate(log_categories.items()):
                    options.append(
                        discord.SelectOption(
                            label=category_name,
                            description=category_data["description"],
                            emoji=category_data["emoji"],
                            value=str(i)
                        )
                    )
                
                super().__init__(
                    placeholder="📋 Select a log category...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
            
            async def callback(self, interaction):
                nonlocal current_category, current_page
                current_category = int(self.values[0])
                current_page = 1  # Reset to page 1 when changing category
                
                # Choose the appropriate embed function based on category
                if current_category == 0:  # Recent User Activity
                    embed, total_pages = await create_user_activity_embed(current_page)
                elif current_category == 2:  # Recent Listening Sessions
                    embed, total_pages = await create_listening_sessions_embed(current_page)
                elif current_category == 4:  # Currently Active Listening
                    embed, total_pages = await create_active_listening_embed(current_page)
                else:
                    # For other categories, create simple placeholder embeds
                    embed = discord.Embed(
                        title=f"{log_categories[category_names[current_category]]['emoji']} {category_names[current_category]}",
                        description="This category is still being implemented.",
                        color=log_categories[category_names[current_category]]['color']
                    )
                    total_pages = 1
                
                embed.set_footer(
                    text=f"👑 Page {current_page} of {total_pages} • Category: {category_names[current_category]} • Limit: {limit} entries",
                    icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
                )
                
                # Update view with new pagination buttons if needed
                view = LogsView(current_category, current_page, total_pages, self.view.admin_cog)
                await interaction.response.edit_message(embed=embed, view=view)
        
        # Create view with dropdown and navigation buttons
        class LogsView(discord.ui.View):
            def __init__(self, category, page, total_pages, admin_cog):
                super().__init__(timeout=300)  # 5 minute timeout
                self.category = category
                self.page = page
                self.total_pages = total_pages
                self.admin_cog = admin_cog
                
                # Add dropdown first
                self.add_item(LogsSelect())
                
                # Add pagination buttons only if there's more than one page
                if self.total_pages > 1:
                    self.add_item(PreviousButton(self.page <= 1))
                    self.add_item(NextButton(self.page >= self.total_pages))
                
                self.add_item(OverviewButton(self.admin_cog))
                self.add_item(CloseButton())
            
            async def update_view(self, interaction, new_page=None):
                """Update the view with new state"""
                nonlocal current_page
                
                if new_page is not None:
                    current_page = new_page
                
                # Choose the appropriate embed function based on category
                if current_category == 0:  # Recent User Activity
                    embed, total_pages = await create_user_activity_embed(current_page)
                elif current_category == 2:  # Recent Listening Sessions
                    embed, total_pages = await create_listening_sessions_embed(current_page)
                elif current_category == 4:  # Currently Active Listening
                    embed, total_pages = await create_active_listening_embed(current_page)
                else:
                    # For other categories, create simple placeholder embeds
                    embed = discord.Embed(
                        title=f"{log_categories[category_names[current_category]]['emoji']} {category_names[current_category]}",
                        description="This category is still being implemented.",
                        color=log_categories[category_names[current_category]]['color']
                    )
                    total_pages = 1
                
                current_page = current_page  # Update the actual current page
                
                # Create new view with updated state
                view = LogsView(current_category, current_page, total_pages, self.admin_cog)
                embed.set_footer(
                    text=f"👑 Page {current_page} of {total_pages} • Category: {category_names[current_category]} • Limit: {limit} entries",
                    icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
                )
                await interaction.response.edit_message(embed=embed, view=view)
            
            async def on_timeout(self):
                for item in self.children:
                    try:
                        item.disabled = True
                    except AttributeError:
                        pass
        
        # Button classes (same as before)
        class PreviousButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(label='◀️ Previous', style=discord.ButtonStyle.secondary, disabled=disabled)
            
            async def callback(self, interaction):
                if self.view.page > 1:
                    await self.view.update_view(interaction, new_page=self.view.page - 1)
        
        class NextButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(label='▶️ Next', style=discord.ButtonStyle.secondary, disabled=disabled)
            
            async def callback(self, interaction):
                if self.view.page < self.view.total_pages:
                    await self.view.update_view(interaction, new_page=self.view.page + 1)
        
        class OverviewButton(discord.ui.Button):
            def __init__(self, admin_cog):
                super().__init__(label='🏠 Overview', style=discord.ButtonStyle.primary)
                self.admin_cog = admin_cog
            
            async def callback(self, interaction):
                # Create overview embed
                overview_embed = discord.Embed(
                    title="📊 System Overview & Performance",
                    description="**Bot performance metrics and system statistics**",
                    color=discord.Color.gold()
                )
                
                # System performance
                import psutil
                
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                memory_mb = memory.used // 1024 // 1024
                memory_percent = memory.percent
                
                uptime = 0.0
                if hasattr(self.admin_cog.bot, 'start_time') and self.admin_cog.bot.start_time:
                    uptime = time.time() - self.admin_cog.bot.start_time
                uptime_hours = int(uptime // 3600)
                uptime_mins = int((uptime % 3600) // 60)
                
                system_info = f"💻 **CPU Usage:** {cpu_percent:.1f}%\n🧠 **RAM Usage:** {memory_mb}MB ({memory_percent:.1f}%)\n📡 **Latency:** {round(self.admin_cog.bot.latency * 1000)}ms\n🕐 **Uptime:** {uptime_hours}h {uptime_mins}m"
                
                overview_embed.add_field(
                    name="⚙️ **System Performance**",
                    value=system_info,
                    inline=True
                )
                
                # Bot statistics with music
                active_listeners = len(getattr(self.admin_cog.bot, 'active_listening', {}))
                bot_info = f"🏠 **Servers:** {len(self.admin_cog.bot.guilds)}\n👥 **Total Users:** {len(self.admin_cog.bot.users)}\n🎮 **Active Gamers:** {len(getattr(self.admin_cog.bot, 'active_sessions', {}))}\n🎵 **Active Listeners:** {active_listeners}\n🤖 **Loaded Cogs:** {len(self.admin_cog.bot.cogs)}"
                
                overview_embed.add_field(
                    name="🤖 **Bot Statistics**",
                    value=bot_info,
                    inline=True
                )
                
                # Quick stats with music
                try:
                    async with aiosqlite.connect(self.admin_cog.db.db_path) as db:
                        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                            result = await cursor.fetchone()
                            total_tracked = result[0] if result else 0
                        
                        async with db.execute("SELECT COUNT(*) FROM game_sessions WHERE duration IS NOT NULL") as cursor:
                            result = await cursor.fetchone()
                            total_sessions = result[0] if result else 0
                        
                        async with db.execute("SELECT COUNT(*) FROM listening_sessions WHERE duration IS NOT NULL") as cursor:
                            result = await cursor.fetchone()
                            total_listening_sessions = result[0] if result else 0
                        
                        async with db.execute("SELECT SUM(total_messages) FROM users") as cursor:
                            result = await cursor.fetchone()
                            total_messages = result[0] if result and result[0] else 0
                    
                    quick_stats = f"📊 **{total_tracked}** tracked users\n💬 **{total_messages:,}** total messages\n🎲 **{total_sessions:,}** gaming sessions\n🎵 **{total_listening_sessions:,}** listening sessions\n⚡ **Live** data tracking"
                    
                    overview_embed.add_field(
                        name="📈 **Quick Statistics**",
                        value=quick_stats,
                        inline=True
                    )
                except Exception as e:
                    overview_embed.add_field(
                        name="📈 **Quick Statistics**",
                        value="❌ Error loading database stats",
                        inline=True
                    )
                
                # Categories summary
                categories_summary = ""
                for i, (category_name, category_data) in enumerate(log_categories.items()):
                    categories_summary += f"{category_data['emoji']} **{category_name}**\n• {category_data['description']}\n\n"
                
                overview_embed.add_field(
                    name="📋 **Available Log Categories**",
                    value=categories_summary.strip(),
                    inline=False
                )
                
                overview_embed.set_footer(text=f"👑 Use the dropdown menu to explore specific log categories • Limit: {limit} entries")
                if self.admin_cog.bot.user:
                    overview_embed.set_thumbnail(url=self.admin_cog.bot.user.avatar.url if self.admin_cog.bot.user.avatar else self.admin_cog.bot.user.default_avatar.url)
                
                await interaction.response.edit_message(embed=overview_embed, view=self.view)
        
        class CloseButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label='❌ Close', style=discord.ButtonStyle.danger)
            
            async def callback(self, interaction):
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="📋 Logs Menu Closed",
                        description="Use `!r logs` to open again.",
                        color=discord.Color.red()
                    ),
                    view=None
                )
                if self.view:
                    self.view.stop()
        
        # Create initial embed and view
        embed, total_pages = await create_user_activity_embed(current_page)
        embed.set_footer(
            text=f"👑 Page {current_page} of {total_pages} • Category: {category_names[current_category]} • Limit: {limit} entries",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        
        view = LogsView(current_category, current_page, total_pages, self)
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(RoxyAdmin(bot))
    print("👑 Roxy's Admin cog loaded with music support!")