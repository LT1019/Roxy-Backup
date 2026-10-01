import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Roxy's owner - set ADMIN_USER_ID in .env to override
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
    """Command check for Roxy's owner - silent for everyone else"""
    async def predicate(ctx):
        if not is_admin_id(ctx.author.id):
            # Log owner command attempts by others (for security)
            print(f"🚫 Non-owner {ctx.author} ({ctx.author.id}) tried to use owner command: {ctx.command}")
            return False
        return True
    return commands.check(predicate)


def is_server_admin(member) -> bool:
    """True if this member is an Admin of their server: the server owner or anyone with Administrator permission"""
    guild = getattr(member, 'guild', None)
    if guild is None:
        return False
    return member.id == guild.owner_id or member.guild_permissions.administrator


def is_owner_or_server_admin():
    """Command check: Roxy's owner anywhere, or an Admin of the server the command is used in - silent for others"""
    async def predicate(ctx):
        if is_admin_id(ctx.author.id) or (ctx.guild and is_server_admin(ctx.author)):
            return True
        print(f"🚫 {ctx.author} ({ctx.author.id}) tried to use server-admin command: {ctx.command}")
        return False
    return commands.check(predicate)
