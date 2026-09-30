import os
from discord.ext import commands
from dotenv import load_dotenv
from config import is_admin_id

load_dotenv()

# Patrons are recognized by the role Patreon gives them in Roxy's own server.
# Role names can be changed in .env if the roles are named differently.
PATRON_GUILD_ID = int(os.getenv('PATRON_GUILD_ID', '1403367039267115118'))

# Highest tier first - a member with several tier roles gets the highest one
TIERS = [
    {
        'key': 'vip',
        'role': os.getenv('PATREON_ROLE_VIP', 'VIP'),
        'name': 'VIP',
        'emoji': '💎',
        'xp_multiplier': 1.5,
        'badges': ['💖 Supporter', '⭐ Fan', '💎 VIP'],
        'title': '💎 Roxy VIP',
        'early_access': True,
    },
    {
        'key': 'fan',
        'role': os.getenv('PATREON_ROLE_FAN', 'Fan'),
        'name': 'Fan',
        'emoji': '⭐',
        'xp_multiplier': 1.25,
        'badges': ['💖 Supporter', '⭐ Fan'],
        'title': None,
        'early_access': False,
    },
    {
        'key': 'supporter',
        'role': os.getenv('PATREON_ROLE_SUPPORTER', 'Supporter'),
        'name': 'Supporter',
        'emoji': '💖',
        'xp_multiplier': 1.0,
        'badges': ['💖 Supporter'],
        'title': None,
        'early_access': False,
    },
]


def get_patron_tier(bot, user_id: int):
    """The user's Patreon tier (dict from TIERS), or None if they aren't a patron"""
    guild = bot.get_guild(PATRON_GUILD_ID)
    member = guild.get_member(user_id) if guild else None
    if member is None:
        return None

    role_names = {role.name.lower() for role in member.roles}
    for tier in TIERS:
        if tier['role'].lower() in role_names:
            return tier
    return None


def xp_multiplier(bot, user_id: int) -> float:
    """XP boost for patrons: 1.25 for Fan, 1.5 for VIP, 1.0 otherwise"""
    tier = get_patron_tier(bot, user_id)
    return tier['xp_multiplier'] if tier else 1.0


def get_patrons(bot):
    """[(member, tier)] for everyone with a tier role, highest tier first"""
    guild = bot.get_guild(PATRON_GUILD_ID)
    if guild is None:
        return []

    patrons = []
    for member in guild.members:
        if member.bot:
            continue
        tier = get_patron_tier(bot, member.id)
        if tier:
            patrons.append((member, tier))
    order = [tier['key'] for tier in TIERS]
    return sorted(patrons, key=lambda p: (order.index(p[1]['key']), p[0].display_name.lower()))


def early_access():
    """Command check: only VIP patrons (and the admin) can use early-access commands"""
    async def predicate(ctx):
        if is_admin_id(ctx.author.id):
            return True
        tier = get_patron_tier(ctx.bot, ctx.author.id)
        if tier and tier['early_access']:
            return True
        await ctx.send("💎 This command is in **early access** for VIP supporters. Use `rr help` to find the Patreon button!", delete_after=10)
        return False
    return commands.check(predicate)
