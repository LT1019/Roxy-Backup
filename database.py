import sqlite3
import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict

# Longest single session that gets credited (24 hours). Longer ones come from stuck or crashed sessions
# (a game left open for days, or a session that was never closed) and would inflate stats.
MAX_SESSION_SECONDS = 24 * 3600

# XP rates (before Patreon boosts)
MESSAGE_XP = 5                   # per minute of chatting - see MESSAGE_XP_COOLDOWN
MESSAGE_XP_COOLDOWN = 60         # seconds - more messages within a minute count, but give no extra XP
GAMING_XP_PER_MINUTE = 1
APP_XP_PER_MINUTE = 1            # same as gaming
VOICE_XP_PER_MINUTE = 25
LISTENING_XP_PER_2_MINUTES = 1

# When each user last got message XP (in memory - resets on restart, which is harmless)
_last_message_xp = {}


def format_duration(seconds) -> str:
    """Readable duration: '21h 17m' from an hour up, '5m 3s' below"""
    seconds = int(seconds or 0)
    if seconds >= 3600:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 60}m {seconds % 60}s"


class RoxyDatabase:
    """Roxy Bot's database management system with progressive XP and music listening tracking"""
    
    def __init__(self, db_path="data/roxy.db"):
        self.db_path = db_path
    
    def get_xp_for_level(self, level):
        """Calculate total XP needed to reach a specific level"""
        if level <= 1:
            return 0
        # Progressive XP: Level N needs (N-1) * N * 50 total XP
        # Level 2: 100 XP, Level 3: 300 XP, Level 4: 600 XP, Level 5: 1000 XP, etc.
        return (level - 1) * level * 50
    
    def calculate_level_from_xp(self, xp):
        """Calculate level from total XP using progressive system"""
        level = 1
        while self.get_xp_for_level(level + 1) <= xp:
            level += 1
        return level
    
    async def init_db(self):
        """Initialize Roxy's database tables"""
        # Create data directory if it doesn't exist
        import os
        os.makedirs("data", exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Users table - Roxy tracks all users (with music listening columns)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    display_name TEXT,
                    join_date TEXT,
                    total_messages INTEGER DEFAULT 0,
                    total_playtime INTEGER DEFAULT 0,
                    current_game TEXT,
                    last_seen TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    total_listening_time INTEGER DEFAULT 0,
                    current_song TEXT,
                    current_artist TEXT
                )
            """)
            
            # Game sessions - Roxy tracks gaming activity
            await db.execute("""
                CREATE TABLE IF NOT EXISTS game_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Music listening sessions - NEW!
            await db.execute("""
                CREATE TABLE IF NOT EXISTS listening_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    song_title TEXT,
                    artist_name TEXT,
                    album_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Daily stats - Roxy's daily analytics (with listening time)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    date TEXT,
                    messages_sent INTEGER DEFAULT 0,
                    playtime INTEGER DEFAULT 0,
                    listening_time INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # App sessions - non-game apps that show as "Playing" (VS Code, YouTube, ...), kept apart from gaming
            await db.execute("""
                CREATE TABLE IF NOT EXISTS app_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    app_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)

            # Voice sessions - time spent in voice channels (AFK channels excluded)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voice_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    channel_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)

            # Roxy's achievements system
            await db.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    achievement_name TEXT,
                    earned_date TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            await db.commit()
            print("✅ Roxy's database initialized successfully!")
    
    async def add_user(self, user_id: int, username: str, display_name: str):
        """Add new user to Roxy's database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check if user exists first
                async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing user
                    await db.execute("""
                        UPDATE users 
                        SET username = ?, display_name = ?, last_seen = ?
                        WHERE user_id = ?
                    """, (username, display_name, datetime.now().isoformat(), user_id))
                else:
                    # Insert new user
                    await db.execute("""
                        INSERT INTO users 
                        (user_id, username, display_name, join_date, last_seen, level, xp, total_listening_time) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, username, display_name, datetime.now().isoformat(), datetime.now().isoformat(), 1, 0, 0))
                
                await db.commit()
                
        except Exception as e:
            print(f"❌ Error in add_user: {e}")
            import traceback
            traceback.print_exc()
    
    async def update_message_count(self, user_id: int, xp_multiplier: float = 1.0) -> int:
        """Update user's message count and XP with progressive leveling"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get current stats
                async with db.execute("""
                    SELECT total_messages, xp, level FROM users WHERE user_id = ?
                """, (user_id,)) as cursor:
                    current_stats = await cursor.fetchone()
                
                if current_stats:
                    current_messages, current_xp, current_level = current_stats
                    
                    # Every message counts, but XP is given at most once per minute (stops spam farming)
                    new_messages = current_messages + 1
                    now = datetime.now()
                    last = _last_message_xp.get(user_id)
                    if last is None or (now - last).total_seconds() >= MESSAGE_XP_COOLDOWN:
                        _last_message_xp[user_id] = now
                        new_xp = current_xp + round(MESSAGE_XP * xp_multiplier)  # Patreon Fan/VIP get boosted XP
                    else:
                        new_xp = current_xp
                    
                    # Calculate new level using progressive system
                    new_level = self.calculate_level_from_xp(new_xp)
                    
                    # Update database
                    await db.execute("""
                        UPDATE users 
                        SET total_messages = ?, 
                            last_seen = ?,
                            xp = ?,
                            level = ?
                        WHERE user_id = ?
                    """, (new_messages, datetime.now().isoformat(), new_xp, new_level, user_id))
                    
                    await db.commit()
                    
                    
                    # Return new level if leveled up
                    if new_level > current_level:
                        return new_level
                else:
                    print(f"❌ User {user_id} not found in database")
                
        except Exception as e:
            print(f"❌ Error in update_message_count: {e}")
            import traceback
            traceback.print_exc()
        
        return 0
    
    async def get_user_stats(self, user_id: int) -> Optional[Tuple]:
        """Get comprehensive user statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT * FROM users WHERE user_id = ?
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result
                    
        except Exception as e:
            print(f"❌ Error in get_user_stats: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # ==================== GAMING SESSION METHODS ====================
    
    async def start_game_session(self, user_id: int, game_name: str):
        """Roxy starts tracking a new game session"""
        try:
            current_time = datetime.now().isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # Update current game
                await db.execute("""
                    UPDATE users SET current_game = ? WHERE user_id = ?
                """, (game_name, user_id))

                # Discard any leftover unfinished session so it can't be closed by mistake later
                await db.execute("""
                    DELETE FROM game_sessions WHERE user_id = ? AND end_time IS NULL
                """, (user_id,))

                # Start new session
                await db.execute("""
                    INSERT INTO game_sessions (user_id, game_name, start_time)
                    VALUES (?, ?, ?)
                """, (user_id, game_name, current_time))
                
                await db.commit()
                
        except Exception as e:
            print(f"❌ Error in start_game_session: {e}")
            import traceback
            traceback.print_exc()
    
    async def end_game_session(self, user_id: int, xp_multiplier: float = 1.0) -> int:
        """Roxy ends current game session and calculates duration"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get the latest unfinished session
                async with db.execute("""
                    SELECT id, start_time, game_name FROM game_sessions 
                    WHERE user_id = ? AND end_time IS NULL 
                    ORDER BY start_time DESC LIMIT 1
                """, (user_id,)) as cursor:
                    session = await cursor.fetchone()
                
                if session:
                    session_id, start_time_str, game_name = session
                    
                    # Parse datetime strings
                    try:
                        start_dt = datetime.fromisoformat(start_time_str)
                        end_dt = datetime.now()
                        duration = int((end_dt - start_dt).total_seconds())
                        
                        
                        # Ensure minimum duration of 1 second
                        if duration < 1:
                            duration = 1
                        # Never credit more than 24 hours for one session (stuck/crashed sessions)
                        duration = min(duration, MAX_SESSION_SECONDS)
                        
                        # Update session with end time and duration
                        await db.execute("""
                            UPDATE game_sessions 
                            SET end_time = ?, duration = ?
                            WHERE id = ?
                        """, (end_dt.isoformat(), duration, session_id))
                        
                        # Add XP for gaming (1 XP per minute, minimum 1 XP)
                        xp_gained = max(1, round((duration // 60) * xp_multiplier))
                        
                        # Get current playtime and XP before updating
                        async with db.execute("""
                            SELECT total_playtime, xp, level FROM users WHERE user_id = ?
                        """, (user_id,)) as cursor:
                            current_stats = await cursor.fetchone()
                            
                        if current_stats:
                            current_playtime, current_xp, current_level = current_stats
                            new_playtime = current_playtime + duration
                            new_xp = current_xp + xp_gained
                            
                            # Calculate new level using progressive system
                            new_level = self.calculate_level_from_xp(new_xp)
                            
                            # Update user stats
                            await db.execute("""
                                UPDATE users 
                                SET total_playtime = ?, 
                                    current_game = NULL,
                                    xp = ?,
                                    level = ?
                                WHERE user_id = ?
                            """, (new_playtime, new_xp, new_level, user_id))
                            
                            
                        
                        await db.commit()
                        
                        return duration
                        
                    except ValueError as e:
                        print(f"❌ Error parsing datetime: {e}")
                        print(f"Start time string: {start_time_str}")
                        return 0
                        
                else:
                    return 0
                    
        except Exception as e:
            print(f"❌ Error in end_game_session: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    # ==================== MUSIC LISTENING SESSION METHODS ====================
    
    async def start_listening_session(self, user_id: int, song_title: str, artist_name: str, album_name: str = None):
        """Roxy starts tracking a new music listening session"""
        try:
            current_time = datetime.now().isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # Update current song and artist
                await db.execute("""
                    UPDATE users SET current_song = ?, current_artist = ? WHERE user_id = ?
                """, (song_title, artist_name, user_id))

                # Discard any leftover unfinished session so it can't be closed by mistake later
                await db.execute("""
                    DELETE FROM listening_sessions WHERE user_id = ? AND end_time IS NULL
                """, (user_id,))

                # Start new listening session
                await db.execute("""
                    INSERT INTO listening_sessions (user_id, song_title, artist_name, album_name, start_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, song_title, artist_name, album_name, current_time))
                
                await db.commit()
                
        except Exception as e:
            print(f"❌ Error in start_listening_session: {e}")
            import traceback
            traceback.print_exc()
    
    async def end_listening_session(self, user_id: int, xp_multiplier: float = 1.0) -> int:
        """Roxy ends current listening session and calculates duration"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get the latest unfinished listening session
                async with db.execute("""
                    SELECT id, start_time, song_title, artist_name FROM listening_sessions 
                    WHERE user_id = ? AND end_time IS NULL 
                    ORDER BY start_time DESC LIMIT 1
                """, (user_id,)) as cursor:
                    session = await cursor.fetchone()
                
                if session:
                    session_id, start_time_str, song_title, artist_name = session
                    
                    # Parse datetime strings
                    try:
                        start_dt = datetime.fromisoformat(start_time_str)
                        end_dt = datetime.now()
                        duration = int((end_dt - start_dt).total_seconds())
                        
                        
                        # Ensure minimum duration of 1 second
                        if duration < 1:
                            duration = 1
                        # Never credit more than 24 hours for one session (stuck/crashed sessions)
                        duration = min(duration, MAX_SESSION_SECONDS)
                        
                        # Update session with end time and duration
                        await db.execute("""
                            UPDATE listening_sessions 
                            SET end_time = ?, duration = ?
                            WHERE id = ?
                        """, (end_dt.isoformat(), duration, session_id))
                        
                        # Add XP for listening (1 XP per 2 minutes, minimum 1 XP)
                        xp_gained = max(1, round((duration // 120) * xp_multiplier))
                        
                        # Get current listening time and XP before updating
                        async with db.execute("""
                            SELECT total_listening_time, xp, level FROM users WHERE user_id = ?
                        """, (user_id,)) as cursor:
                            current_stats = await cursor.fetchone()
                            
                        if current_stats:
                            current_listening_time, current_xp, current_level = current_stats
                            new_listening_time = current_listening_time + duration
                            new_xp = current_xp + xp_gained
                            
                            # Calculate new level using progressive system
                            new_level = self.calculate_level_from_xp(new_xp)
                            
                            # Update user stats
                            await db.execute("""
                                UPDATE users 
                                SET total_listening_time = ?, 
                                    current_song = NULL,
                                    current_artist = NULL,
                                    xp = ?,
                                    level = ?
                                WHERE user_id = ?
                            """, (new_listening_time, new_xp, new_level, user_id))
                            
                            
                        
                        await db.commit()
                        
                        return duration
                        
                    except ValueError as e:
                        print(f"❌ Error parsing datetime: {e}")
                        print(f"Start time string: {start_time_str}")
                        return 0
                        
                else:
                    return 0
                    
        except Exception as e:
            print(f"❌ Error in end_listening_session: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    # ==================== MUSIC ANALYTICS METHODS ====================
    
    async def get_listening_statistics(self, user_id: int) -> Dict:
        """Get comprehensive listening statistics for a user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get total sessions count
                async with db.execute("""
                    SELECT COUNT(*) FROM listening_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    total_sessions = result[0] if result else 0
                
                # Get average session duration
                async with db.execute("""
                    SELECT AVG(duration) FROM listening_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    avg_duration = result[0] if result[0] else 0
                
                # Get longest session
                async with db.execute("""
                    SELECT MAX(duration) FROM listening_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    longest_duration = result[0] if result[0] else 0
                
                # Format the results
                avg_minutes = int(avg_duration // 60) if avg_duration else 0
                avg_seconds = int(avg_duration % 60) if avg_duration else 0
                longest_minutes = int(longest_duration // 60) if longest_duration else 0
                longest_seconds = int(longest_duration % 60) if longest_duration else 0
                
                return {
                    'total_sessions': total_sessions,
                    'avg_session': format_duration(avg_duration) if avg_duration else "No sessions",
                    'longest_session': format_duration(longest_duration) if longest_duration else "No sessions",
                    'avg_duration_seconds': avg_duration,
                    'longest_session_minutes': longest_minutes
                }
                
        except Exception as e:
            print(f"❌ Error in get_listening_statistics: {e}")
            import traceback
            traceback.print_exc()
            return {
                'total_sessions': 0,
                'avg_session': "No data",
                'longest_session': "No data",
                'avg_duration_seconds': 0,
                'longest_session_minutes': 0
            }
    
    async def get_favorite_artists(self, user_id: int, limit: int = 5) -> List[Tuple]:
        """Get user's favorite artists ranked by total listening time"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT 
                        artist_name,
                        SUM(duration) as total_listening_time,
                        COUNT(*) as session_count
                    FROM listening_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                    GROUP BY artist_name
                    ORDER BY total_listening_time DESC
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    result = await cursor.fetchall()
                    return result
                    
        except Exception as e:
            print(f"❌ Error in get_favorite_artists: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_favorite_songs(self, user_id: int, limit: int = 5) -> List[Tuple]:
        """Get user's favorite songs ranked by total listening time"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT 
                        song_title,
                        artist_name,
                        SUM(duration) as total_listening_time,
                        COUNT(*) as play_count
                    FROM listening_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                    GROUP BY song_title, artist_name
                    ORDER BY total_listening_time DESC
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    result = await cursor.fetchall()
                    return result
                    
        except Exception as e:
            print(f"❌ Error in get_favorite_songs: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_recent_listening_history(self, user_id: int, limit: int = 10) -> List[Tuple]:
        """Get user's recent listening history"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT 
                        song_title,
                        artist_name,
                        album_name,
                        end_time,
                        duration
                    FROM listening_sessions 
                    WHERE user_id = ? AND end_time IS NOT NULL AND duration >= 60
                    ORDER BY end_time DESC
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    results = await cursor.fetchall()
                    
                    # Convert end_time strings to datetime objects
                    formatted_results = []
                    for song_title, artist_name, album_name, end_time_str, duration in results:
                        try:
                            end_time = datetime.fromisoformat(end_time_str)
                            formatted_results.append((song_title, artist_name, album_name, end_time, duration))
                        except ValueError:
                            print(f"❌ Error parsing datetime: {end_time_str}")
                            continue
                    
                    return formatted_results
                    
        except Exception as e:
            print(f"❌ Error in get_recent_listening_history: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_user_music_achievements(self, user_id: int) -> List[str]:
        """Get music achievements for a user based on their listening stats"""
        try:
            stats = await self.get_user_stats(user_id)
            if not stats or len(stats) < 11:
                return []
            
            listening_stats = await self.get_listening_statistics(user_id)
            total_listening_time = stats[10] if len(stats) > 10 else 0  # total_listening_time column
            hours = total_listening_time // 3600
            total_sessions = listening_stats['total_sessions']
            longest_session_minutes = listening_stats['longest_session_minutes']
            
            achievements = []
            
            # Listening time milestones
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
            elif hours >= 1:
                achievements.append("🎺 First Listen (1+ hour)")
            
            # Session milestones
            if total_sessions >= 1000:
                achievements.append("🏆 Session Legend (1000+ sessions)")
            elif total_sessions >= 500:
                achievements.append("💎 Session Master (500+ sessions)")
            elif total_sessions >= 100:
                achievements.append("🌟 Session Expert (100+ sessions)")
            elif total_sessions >= 50:
                achievements.append("⭐ Regular Listener (50+ sessions)")
            elif total_sessions >= 10:
                achievements.append("✨ Session Starter (10+ sessions)")
            
            # Marathon listening achievements
            if longest_session_minutes >= 480:  # 8+ hours
                achievements.append("🏃‍♀️ Marathon Listener (8+ hour session)")
            elif longest_session_minutes >= 360:  # 6+ hours
                achievements.append("⏰ Extended Listening (6+ hours)")
            elif longest_session_minutes >= 180:  # 3+ hours
                achievements.append("🕐 Long Session (3+ hours)")
            elif longest_session_minutes >= 120:  # 2+ hours
                achievements.append("⏱️ Focused Listening (2+ hours)")
            elif longest_session_minutes >= 60:  # 1+ hour
                achievements.append("⏲️ Continuous Play (1+ hour)")
            
            # Artist/Song variety achievements
            artist_count = await self.count_distinct_artists(user_id)
            if artist_count >= 50:
                achievements.append("🎨 Music Explorer (50+ artists)")
            elif artist_count >= 20:
                achievements.append("🎯 Diverse Taste (20+ artists)")
            elif artist_count >= 10:
                achievements.append("🎪 Multi-Genre (10+ artists)")

            favorite_artists = await self.get_favorite_artists(user_id, 1)
            
            # Top artist dedication
            if favorite_artists:
                top_artist_time = favorite_artists[0][1]  # listening time in seconds
                top_artist_hours = top_artist_time // 3600
                
                if top_artist_hours >= 50:
                    achievements.append(f"💝 {favorite_artists[0][0]} Superfan (50+ hours)")
                elif top_artist_hours >= 20:
                    achievements.append(f"❤️ {favorite_artists[0][0]} Fan (20+ hours)")
                elif top_artist_hours >= 10:
                    achievements.append(f"😊 Enjoys {favorite_artists[0][0]} (10+ hours)")
            
            return achievements
            
        except Exception as e:
            print(f"❌ Error in get_user_music_achievements: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def count_distinct_artists(self, user_id: int) -> int:
        """Count how many different artists a user has listened to"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT COUNT(DISTINCT artist_name) FROM listening_sessions
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            print(f"❌ Error in count_distinct_artists: {e}")
            return 0

    async def count_distinct_games(self, user_id: int) -> int:
        """Count how many different games a user has played"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT COUNT(DISTINCT game_name) FROM game_sessions
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            print(f"❌ Error in count_distinct_games: {e}")
            return 0

    # ==================== SESSION RECOVERY ====================

    async def discard_unfinished_sessions(self) -> Tuple[int, int]:
        """Discard sessions left open by a crash/restart - their real end time is unknown.
        No XP or time was credited for them yet, so user totals are unaffected."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                game_cursor = await db.execute("DELETE FROM game_sessions WHERE end_time IS NULL")
                listen_cursor = await db.execute("DELETE FROM listening_sessions WHERE end_time IS NULL")
                await db.execute("DELETE FROM app_sessions WHERE end_time IS NULL")
                await db.execute("DELETE FROM voice_sessions WHERE end_time IS NULL")
                await db.execute("UPDATE users SET current_game = NULL, current_song = NULL, current_artist = NULL")
                await db.commit()
                return game_cursor.rowcount, listen_cursor.rowcount
        except Exception as e:
            print(f"❌ Error in discard_unfinished_sessions: {e}")
            return 0, 0

    # ==================== APP SESSIONS (non-game apps) ====================

    async def start_app_session(self, user_id: int, app_name: str):
        """Start tracking time in a non-game app (VS Code, YouTube, ...)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM app_sessions WHERE user_id = ? AND end_time IS NULL", (user_id,))
                await db.execute("INSERT INTO app_sessions (user_id, app_name, start_time) VALUES (?, ?, ?)",
                                 (user_id, app_name, datetime.now().isoformat()))
                await db.commit()
        except Exception as e:
            print(f"❌ Error in start_app_session: {e}")

    async def award_xp(self, db, user_id: int, xp: int):
        """Add XP inside an open connection and recalculate the level"""
        if xp <= 0:
            return
        async with db.execute("SELECT xp FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            new_xp = row[0] + xp
            await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?",
                             (new_xp, self.calculate_level_from_xp(new_xp), user_id))

    async def end_app_session(self, user_id: int, xp_multiplier: float = 1.0) -> int:
        """End the open app session - earns XP like gaming (1 XP per minute)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT id, start_time FROM app_sessions
                    WHERE user_id = ? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1
                """, (user_id,)) as cursor:
                    session = await cursor.fetchone()
                if not session:
                    return 0

                end_dt = datetime.now()
                duration = int((end_dt - datetime.fromisoformat(session[1])).total_seconds())
                duration = min(max(duration, 1), MAX_SESSION_SECONDS)
                await db.execute("UPDATE app_sessions SET end_time = ?, duration = ? WHERE id = ?",
                                 (end_dt.isoformat(), duration, session[0]))
                await self.award_xp(db, user_id, max(1, round((duration // 60) * APP_XP_PER_MINUTE * xp_multiplier)))
                await db.commit()
                return duration
        except Exception as e:
            print(f"❌ Error in end_app_session: {e}")
            return 0

    # ==================== VOICE SESSIONS ====================

    async def start_voice_session(self, user_id: int, guild_id: int, channel_name: str):
        """Start tracking time in a voice channel"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM voice_sessions WHERE user_id = ? AND end_time IS NULL", (user_id,))
                await db.execute("INSERT INTO voice_sessions (user_id, guild_id, channel_name, start_time) VALUES (?, ?, ?, ?)",
                                 (user_id, guild_id, channel_name, datetime.now().isoformat()))
                await db.commit()
        except Exception as e:
            print(f"❌ Error in start_voice_session: {e}")

    async def end_voice_session(self, user_id: int, xp_multiplier: float = 1.0) -> int:
        """End the open voice session (capped at 24 hours) - 25 XP per full minute"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT id, start_time FROM voice_sessions
                    WHERE user_id = ? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1
                """, (user_id,)) as cursor:
                    session = await cursor.fetchone()
                if not session:
                    return 0

                end_dt = datetime.now()
                duration = int((end_dt - datetime.fromisoformat(session[1])).total_seconds())
                duration = min(max(duration, 1), MAX_SESSION_SECONDS)
                await db.execute("UPDATE voice_sessions SET end_time = ?, duration = ? WHERE id = ?",
                                 (end_dt.isoformat(), duration, session[0]))
                # Full minutes only, so hopping in and out of a call gives nothing
                await self.award_xp(db, user_id, round((duration // 60) * VOICE_XP_PER_MINUTE * xp_multiplier))
                await db.commit()
                return duration
        except Exception as e:
            print(f"❌ Error in end_voice_session: {e}")
            return 0

    async def get_voice_stats(self, user_id: int) -> Dict:
        """Total voice time, number of calls and longest call"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT COALESCE(SUM(duration), 0), COUNT(*), COALESCE(MAX(duration), 0) FROM voice_sessions
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    total_seconds, sessions, longest = await cursor.fetchone()
            return {'total_seconds': total_seconds, 'sessions': sessions, 'longest_seconds': longest}
        except Exception as e:
            print(f"❌ Error in get_voice_stats: {e}")
            return {'total_seconds': 0, 'sessions': 0, 'longest_seconds': 0}

    async def get_app_stats(self, user_id: int) -> Dict:
        """Total app time, favorite apps and recent app sessions for rr apps"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT COALESCE(SUM(duration), 0), COUNT(*) FROM app_sessions
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    total_seconds, sessions = await cursor.fetchone()
                async with db.execute("""
                    SELECT app_name, SUM(duration) AS total, COUNT(*) FROM app_sessions
                    WHERE user_id = ? AND duration IS NOT NULL
                    GROUP BY app_name ORDER BY total DESC LIMIT 10
                """, (user_id,)) as cursor:
                    favorites = await cursor.fetchall()
                async with db.execute("""
                    SELECT app_name, end_time, duration FROM app_sessions
                    WHERE user_id = ? AND end_time IS NOT NULL AND duration >= 60
                    ORDER BY end_time DESC LIMIT 5
                """, (user_id,)) as cursor:
                    recent = [(name, datetime.fromisoformat(end), duration) for name, end, duration in await cursor.fetchall()]
            return {'total_seconds': total_seconds, 'sessions': sessions, 'favorites': favorites, 'recent': recent}
        except Exception as e:
            print(f"❌ Error in get_app_stats: {e}")
            return {'total_seconds': 0, 'sessions': 0, 'favorites': [], 'recent': []}

    # ==================== LEADERBOARD METHODS ====================
    
    async def get_leaderboard(self, category: str, limit: int = 10) -> List[Tuple]:
        """Get Roxy's leaderboards"""
        valid_categories = {
            'messages': 'total_messages',
            'playtime': 'total_playtime',
            'listening': 'total_listening_time',
            'level': 'level',
            'xp': 'xp'
        }
        
        if category not in valid_categories:
            print(f"❌ Invalid leaderboard category: {category}")
            return []
        
        try:
            column = valid_categories[category]
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(f"""
                    SELECT user_id, username, display_name, {column}
                    FROM users 
                    WHERE {column} > 0
                    ORDER BY {column} DESC, xp DESC
                    LIMIT ?
                """, (limit,)) as cursor:
                    result = await cursor.fetchall()
                    return result
                    
        except Exception as e:
            print(f"❌ Error in get_leaderboard: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def force_refresh_user_stats(self, user_id: int):
        """Force refresh user stats (for debugging)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Recalculate total playtime from sessions
                async with db.execute("""
                    SELECT SUM(duration) FROM game_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    total_playtime = result[0] if result[0] else 0
                
                # Recalculate total listening time from sessions
                async with db.execute("""
                    SELECT SUM(duration) FROM listening_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    total_listening_time = result[0] if result[0] else 0
                
                # Get current XP to recalculate level
                async with db.execute("""
                    SELECT xp FROM users WHERE user_id = ?
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    current_xp = result[0] if result else 0
                
                # Recalculate level using progressive system
                new_level = self.calculate_level_from_xp(current_xp)
                
                # Update user record
                await db.execute("""
                    UPDATE users SET total_playtime = ?, total_listening_time = ?, level = ? WHERE user_id = ?
                """, (total_playtime, total_listening_time, new_level, user_id))
                
                await db.commit()
                return total_playtime, total_listening_time
                
        except Exception as e:
            print(f"❌ Error in force_refresh_user_stats: {e}")
            return 0, 0
    
    # ==================== EXISTING GAMING METHODS (unchanged) ====================
    
    async def get_session_statistics(self, user_id: int) -> Dict:
        """Get comprehensive session statistics for a user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get total sessions count
                async with db.execute("""
                    SELECT COUNT(*) FROM game_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    total_sessions = result[0] if result else 0
                
                # Get average session duration
                async with db.execute("""
                    SELECT AVG(duration) FROM game_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    avg_duration = result[0] if result[0] else 0
                
                # Get longest session
                async with db.execute("""
                    SELECT MAX(duration) FROM game_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                """, (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    longest_duration = result[0] if result[0] else 0
                
                # Format the results
                avg_minutes = int(avg_duration // 60) if avg_duration else 0
                avg_seconds = int(avg_duration % 60) if avg_duration else 0
                longest_minutes = int(longest_duration // 60) if longest_duration else 0
                longest_seconds = int(longest_duration % 60) if longest_duration else 0
                
                return {
                    'total_sessions': total_sessions,
                    'avg_session': format_duration(avg_duration) if avg_duration else "No sessions",
                    'longest_session': format_duration(longest_duration) if longest_duration else "No sessions",
                    'avg_duration_seconds': avg_duration,
                    'longest_session_minutes': longest_minutes
                }
                
        except Exception as e:
            print(f"❌ Error in get_session_statistics: {e}")
            import traceback
            traceback.print_exc()
            return {
                'total_sessions': 0,
                'avg_session': "No data",
                'longest_session': "No data",
                'avg_duration_seconds': 0,
                'longest_session_minutes': 0
            }
    
    async def get_favorite_games(self, user_id: int, limit: int = 5) -> List[Tuple]:
        """Get user's favorite games ranked by total playtime"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT 
                        game_name,
                        SUM(duration) as total_playtime,
                        COUNT(*) as session_count
                    FROM game_sessions 
                    WHERE user_id = ? AND duration IS NOT NULL
                    GROUP BY game_name
                    ORDER BY total_playtime DESC
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    result = await cursor.fetchall()
                    return result
                    
        except Exception as e:
            print(f"❌ Error in get_favorite_games: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_recent_game_history(self, user_id: int, limit: int = 10) -> List[Tuple]:
        """Get user's recent gaming history"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT 
                        game_name,
                        end_time,
                        duration
                    FROM game_sessions 
                    WHERE user_id = ? AND end_time IS NOT NULL AND duration >= 60
                    ORDER BY end_time DESC
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    results = await cursor.fetchall()
                    
                    # Convert end_time strings to datetime objects
                    formatted_results = []
                    for game_name, end_time_str, duration in results:
                        try:
                            end_time = datetime.fromisoformat(end_time_str)
                            formatted_results.append((game_name, end_time, duration))
                        except ValueError:
                            print(f"❌ Error parsing datetime: {end_time_str}")
                            continue
                    
                    return formatted_results
                    
        except Exception as e:
            print(f"❌ Error in get_recent_game_history: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_user_gaming_achievements(self, user_id: int) -> List[str]:
        """Get gaming achievements for a user based on their stats"""
        try:
            stats = await self.get_user_stats(user_id)
            if not stats:
                return []
            
            session_stats = await self.get_session_statistics(user_id)
            total_playtime = stats[5]  # total_playtime column
            hours = total_playtime // 3600
            total_sessions = session_stats['total_sessions']
            longest_session_minutes = session_stats['longest_session_minutes']
            
            achievements = []
            
            # Playtime milestones
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
            elif hours >= 1:
                achievements.append("🌱 Gaming Started (1+ hour)")
            
            # Session milestones
            if total_sessions >= 100:
                achievements.append("🎲 Session Master (100+ sessions)")
            elif total_sessions >= 50:
                achievements.append("🎯 Session Expert (50+ sessions)")
            elif total_sessions >= 20:
                achievements.append("🎮 Regular Gamer (20+ sessions)")
            elif total_sessions >= 10:
                achievements.append("🕹️ Session Starter (10+ sessions)")
            elif total_sessions >= 5:
                achievements.append("🎪 Getting Started (5+ sessions)")
            
            # Marathon session achievements
            if longest_session_minutes >= 360:  # 6+ hours
                achievements.append("🏃‍♂️ Ultra Marathon (6+ hour session)")
            elif longest_session_minutes >= 300:  # 5+ hours
                achievements.append("⏰ Marathon Gamer (5+ hour session)")
            elif longest_session_minutes >= 180:  # 3+ hours
                achievements.append("🕐 Extended Session (3+ hours)")
            elif longest_session_minutes >= 120:  # 2+ hours
                achievements.append("⏱️ Long Session (2+ hours)")
            elif longest_session_minutes >= 60:  # 1+ hour
                achievements.append("⏲️ Focused Session (1+ hour)")
            
            # Get favorite games for game-specific achievements
            favorite_games = await self.get_favorite_games(user_id, 1)
            if favorite_games:
                top_game_playtime = favorite_games[0][1]  # playtime in seconds
                top_game_hours = top_game_playtime // 3600
                
                if top_game_hours >= 20:
                    achievements.append(f"💝 Devoted to {favorite_games[0][0]} (20+ hours)")
                elif top_game_hours >= 10:
                    achievements.append(f"❤️ Loves {favorite_games[0][0]} (10+ hours)")
                elif top_game_hours >= 5:
                    achievements.append(f"😊 Enjoys {favorite_games[0][0]} (5+ hours)")
            
            # Variety achievements
            game_count = await self.count_distinct_games(user_id)
            if game_count >= 10:
                achievements.append("🎨 Game Variety Expert (10+ games)")
            elif game_count >= 5:
                achievements.append("🎯 Game Explorer (5+ games)")
            elif game_count >= 3:
                achievements.append("🎪 Multi-Gamer (3+ games)")
            
            return achievements
            
        except Exception as e:
            print(f"❌ Error in get_user_gaming_achievements: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    # ==================== ADMIN FUNCTIONS ====================
    
    async def force_set_user_xp(self, user_id: int, xp: int, level: int = None):
        """Force set user XP and recalculate level (Admin only)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # If level not provided, calculate it from XP
                if level is None:
                    level = self.calculate_level_from_xp(xp)
                
                await db.execute("""
                    UPDATE users 
                    SET xp = ?, level = ?
                    WHERE user_id = ?
                """, (xp, level, user_id))
                
                await db.commit()
                print(f"👑 Admin set user {user_id} to {xp} XP, level {level}")
                
        except Exception as e:
            print(f"❌ Error in force_set_user_xp: {e}")
            import traceback
            traceback.print_exc()
    
    async def reset_user_stats(self, user_id: int):
        """Reset all user stats (Admin only)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Reset user stats
                await db.execute("""
                    UPDATE users 
                    SET total_messages = 0, 
                        total_playtime = 0, 
                        total_listening_time = 0,
                        current_game = NULL,
                        current_song = NULL,
                        current_artist = NULL,
                        level = 1,
                        xp = 0
                    WHERE user_id = ?
                """, (user_id,))
                
                # Delete all game sessions for this user
                await db.execute("""
                    DELETE FROM game_sessions WHERE user_id = ?
                """, (user_id,))
                
                # Delete all listening sessions for this user
                await db.execute("""
                    DELETE FROM listening_sessions WHERE user_id = ?
                """, (user_id,))
                
                # Delete all app sessions for this user
                await db.execute("DELETE FROM app_sessions WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM voice_sessions WHERE user_id = ?", (user_id,))
                
                # Delete achievements
                await db.execute("""
                    DELETE FROM achievements WHERE user_id = ?
                """, (user_id,))
                
                await db.commit()
                print(f"👑 Admin reset all stats for user {user_id}")
                
        except Exception as e:
            print(f"❌ Error in reset_user_stats: {e}")
            import traceback
            traceback.print_exc()
    
    async def get_database_stats(self) -> Dict:
        """Get comprehensive database statistics (Admin only)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                
                # Total users
                async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                    result = await cursor.fetchone()
                    stats['total_users'] = result[0] if result else 0
                
                # Total messages
                async with db.execute("SELECT SUM(total_messages) FROM users") as cursor:
                    result = await cursor.fetchone()
                    stats['total_messages'] = result[0] if result[0] else 0
                
                # Total playtime in hours
                async with db.execute("SELECT SUM(total_playtime) FROM users") as cursor:
                    result = await cursor.fetchone()
                    total_seconds = result[0] if result[0] else 0
                    stats['total_playtime_hours'] = round(total_seconds / 3600, 1)
                
                # Total listening time in hours
                async with db.execute("SELECT SUM(total_listening_time) FROM users") as cursor:
                    result = await cursor.fetchone()
                    total_seconds = result[0] if result[0] else 0
                    stats['total_listening_hours'] = round(total_seconds / 3600, 1)
                
                # Total game sessions
                async with db.execute("SELECT COUNT(*) FROM game_sessions") as cursor:
                    result = await cursor.fetchone()
                    stats['total_sessions'] = result[0] if result else 0
                
                # Total listening sessions
                async with db.execute("SELECT COUNT(*) FROM listening_sessions") as cursor:
                    result = await cursor.fetchone()
                    stats['total_listening_sessions'] = result[0] if result else 0
                
                # Highest level
                async with db.execute("SELECT MAX(level) FROM users") as cursor:
                    result = await cursor.fetchone()
                    stats['highest_level'] = result[0] if result[0] else 1
                
                # Average level
                async with db.execute("SELECT AVG(level) FROM users") as cursor:
                    result = await cursor.fetchone()
                    stats['avg_level'] = result[0] if result[0] else 1.0
                
                # Max XP
                async with db.execute("SELECT MAX(xp) FROM users") as cursor:
                    result = await cursor.fetchone()
                    stats['max_xp'] = result[0] if result[0] else 0
                
                # Active users (last 7 days)
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                async with db.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE last_seen > ?
                """, (week_ago,)) as cursor:
                    result = await cursor.fetchone()
                    stats['active_users'] = result[0] if result else 0
                
                return stats
                
        except Exception as e:
            print(f"❌ Error in get_database_stats: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    async def cleanup_inactive_users(self, days_inactive: int = 30) -> int:
        """Remove users inactive for X days (Admin only)"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_inactive)).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # Get count of users to be deleted
                async with db.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE last_seen < ? AND total_messages = 0 AND total_playtime = 0 AND total_listening_time = 0
                """, (cutoff_date,)) as cursor:
                    result = await cursor.fetchone()
                    count_to_delete = result[0] if result else 0
                
                if count_to_delete > 0:
                    # Delete inactive users with 0 messages
                    await db.execute("""
                        DELETE FROM users 
                        WHERE last_seen < ? AND total_messages = 0 AND total_playtime = 0 AND total_listening_time = 0
                    """, (cutoff_date,))
                    
                    await db.commit()
                    print(f"👑 Admin cleanup: Removed {count_to_delete} inactive users")
                    return count_to_delete
                else:
                    print(f"👑 Admin cleanup: No inactive users to remove")
                    return 0
                
        except Exception as e:
            print(f"❌ Error in cleanup_inactive_users: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    async def get_all_users_admin(self, limit: int = 50) -> List[Tuple]:
        """Get all users for admin review"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT user_id, display_name, total_messages, total_playtime, total_listening_time, level, xp, last_seen
                    FROM users 
                    ORDER BY xp DESC 
                    LIMIT ?
                """, (limit,)) as cursor:
                    result = await cursor.fetchall()
                    return result
                    
        except Exception as e:
            print(f"❌ Error in get_all_users_admin: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def backup_database(self) -> str:
        """Create database backup (Admin only)"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"data/roxy_backup_{timestamp}.db"

            # SQLite's online backup API is safe even while Roxy is writing
            async with aiosqlite.connect(self.db_path) as source, aiosqlite.connect(backup_path) as target:
                await source.backup(target)

            print(f"👑 Database backup created: {backup_path}")
            return backup_path

        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            return ""

    async def add_xp(self, user_id: int, amount: int) -> Optional[Tuple[int, int]]:
        """Add (or remove, if negative) XP and recalculate level (Admin only).
        Returns (new_xp, new_level), or None if the user isn't tracked."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT xp FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    result = await cursor.fetchone()
                if not result:
                    return None

                new_xp = max(0, result[0] + amount)
                new_level = self.calculate_level_from_xp(new_xp)
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user_id))
                await db.commit()
                print(f"👑 Admin changed user {user_id} XP by {amount} → {new_xp} XP, level {new_level}")
                return new_xp, new_level

        except Exception as e:
            print(f"❌ Error in add_xp: {e}")
            return None

    # ==================== CUSTOM ACHIEVEMENTS ====================

    async def give_achievement(self, user_id: int, achievement_name: str) -> bool:
        """Grant a custom achievement. Returns False if the user already has it."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT 1 FROM achievements WHERE user_id = ? AND achievement_name = ?
                """, (user_id, achievement_name)) as cursor:
                    if await cursor.fetchone():
                        return False

                await db.execute("""
                    INSERT INTO achievements (user_id, achievement_name, earned_date) VALUES (?, ?, ?)
                """, (user_id, achievement_name, datetime.now().isoformat()))
                await db.commit()
                return True

        except Exception as e:
            print(f"❌ Error in give_achievement: {e}")
            return False

    async def remove_achievement(self, user_id: int, achievement_name: str) -> bool:
        """Remove a custom achievement. Returns False if the user didn't have it."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM achievements WHERE user_id = ? AND achievement_name = ?
                """, (user_id, achievement_name))
                await db.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"❌ Error in remove_achievement: {e}")
            return False

    async def get_user_custom_achievements(self, user_id: int) -> List[Tuple[str, str]]:
        """Get (achievement_name, earned_date) for a user's granted achievements"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT achievement_name, earned_date FROM achievements
                    WHERE user_id = ? ORDER BY earned_date
                """, (user_id,)) as cursor:
                    return await cursor.fetchall()

        except Exception as e:
            print(f"❌ Error in get_user_custom_achievements: {e}")
            return []

    async def get_achievement_holders(self, achievement_name: str) -> List[Tuple[int, str, str]]:
        """Get (user_id, display_name, earned_date) for everyone with an achievement"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT achievements.user_id, users.display_name, achievements.earned_date
                    FROM achievements
                    LEFT JOIN users ON achievements.user_id = users.user_id
                    WHERE achievements.achievement_name = ?
                    ORDER BY achievements.earned_date
                """, (achievement_name,)) as cursor:
                    return await cursor.fetchall()

        except Exception as e:
            print(f"❌ Error in get_achievement_holders: {e}")
            return []    
    # ==================== EXPORT ====================
    
    async def export_tables(self) -> Dict[str, Tuple[List[str], List[Tuple]]]:
        """Every table's column names and rows, for the admin Excel export"""
        tables = {}
        async with aiosqlite.connect(self.db_path) as db:
            for table in ['users', 'game_sessions', 'listening_sessions', 'app_sessions', 'voice_sessions', 'achievements', 'daily_stats']:
                async with db.execute(f"SELECT * FROM {table}") as cursor:
                    columns = [description[0] for description in cursor.description]
                    tables[table] = (columns, await cursor.fetchall())
        return tables

    
    # ==================== PRIVACY ====================
    
    USER_DATA_TABLES = ['game_sessions', 'listening_sessions', 'app_sessions', 'voice_sessions', 'achievements', 'daily_stats', 'users']
    
    async def delete_user_data(self, user_id: int) -> Dict[str, int]:
        """Permanently delete everything stored about a user. Returns rows deleted per table."""
        deleted = {}
        async with aiosqlite.connect(self.db_path) as db:
            for table in self.USER_DATA_TABLES:
                cursor = await db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
                deleted[table] = cursor.rowcount
            await db.commit()
        return deleted

