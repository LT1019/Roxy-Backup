import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Roxy's administrator - set ADMIN_USER_ID in .env to override
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '526795891487670302'))

# Donation pages shown as buttons under rr help - leave unset to hide a button
DONATE_LINKS = [
    (label, url) for label, url in (
        ('☕ Ko-fi', os.getenv('KOFI_URL', '').strip()),
        ('💖 Patreon', os.getenv('PATREON_URL', '').strip()),
    ) if url.startswith('https://')
]


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
