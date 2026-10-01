import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Roxy's administrator - set ADMIN_USER_ID in .env to override
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '526795891487670302'))

# Link buttons shown under rr help and rr info - leave a value unset in .env to hide its button
LINK_BUTTONS = [
    (label, url) for label, url in (
        ('➕ Invite Roxy', os.getenv('INVITE_URL', '').strip()),
        ('☕ Ko-fi - Support Roxy', os.getenv('KOFI_URL', '').strip()),
        ('💖 Patreon - Support Roxy', os.getenv('PATREON_URL', '').strip()),
        ('💬 Support', os.getenv('SUPPORT_SERVER_URL', '').strip()),
    ) if url.startswith('https://')
]

# Apps that show up as "Playing" in Discord but aren't games - tracked separately as app time (rr apps),
# never as gaming. Add more without code changes: APP_ACTIVITIES=App One,App Two in .env
APP_ACTIVITIES = {name.strip().lower() for name in [
    # Coding and creative tools
    'Visual Studio Code', 'Visual Studio', 'Cursor', 'PyCharm', 'IntelliJ IDEA', 'Android Studio', 'GitHub',
    'GitHub Desktop', 'Blender', 'Adobe Photoshop', 'Photoshop', 'CLIP STUDIO PAINT', 'OBS Studio', 'Serato DJ Pro',
    # Browsers, websites and streaming
    'Google Chrome', 'Google', 'Microsoft Edge', 'Firefox', 'Brave', 'Opera GX', 'YouTube', 'YouTube Music', 'Twitch',
    'X.com', 'Netflix', 'Crunchyroll', 'Disney+', 'Prime Video', 'animepahe', 'MyAnimeList', 'AniList', 'Simkl', 'mpv',
    'VLC media player', 'Apple', 'Spotify',
    # Launchers and tools
    'Steam', 'Epic Games Launcher', 'Battle.net', 'CurseForge', 'Medal', 'Valorant Tracker App', 'Auto Clicker',
    'Wallpaper Engine', 'Discord',
] + os.getenv('APP_ACTIVITIES', '').split(',') if name.strip()}


def is_admin_id(user_id: int) -> bool:
    """True if this Discord user is Roxy's admin"""
    return user_id == ADMIN_USER_ID


def is_admin():
    """Command check for Roxy's admin - silent for non-admins"""
    async def predicate(ctx):
        if not is_admin_id(ctx.author.id):
            # Log admin command attempts by non-admins (for security)
            print(f"🚫 Non-admin {ctx.author} ({ctx.author.id}) tried to use admin command: {ctx.command}")
            return False
        return True
    return commands.check(predicate)
