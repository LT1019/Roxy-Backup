import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Roxy's administrator - set ADMIN_USER_ID in .env to override
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '526795891487670302'))


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
