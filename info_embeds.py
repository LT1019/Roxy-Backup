import discord

# Discord badge names for member.public_flags
BADGES = {
    'staff': '👔 Discord Staff',
    'partner': '🤝 Partnered Server Owner',
    'hypesquad': '🎉 HypeSquad Events',
    'bug_hunter': '🐛 Bug Hunter',
    'bug_hunter_level_2': '🐛 Bug Hunter Gold',
    'hypesquad_bravery': '🟣 HypeSquad Bravery',
    'hypesquad_brilliance': '🟠 HypeSquad Brilliance',
    'hypesquad_balance': '🟢 HypeSquad Balance',
    'early_supporter': '💎 Early Supporter',
    'verified_bot': '✅ Verified Bot',
    'verified_bot_developer': '🛠️ Early Verified Bot Developer',
    'discord_certified_moderator': '🛡️ Moderator Programs Alumni',
    'active_developer': '👨‍💻 Active Developer',
}

STATUS = {
    discord.Status.online: '🟢 Online',
    discord.Status.idle: '🌙 Idle',
    discord.Status.dnd: '⛔ Do Not Disturb',
    discord.Status.offline: '⚫ Offline',
}


def fmt_date(dt):
    """Discord timestamp: full date plus relative time"""
    return f"<t:{int(dt.timestamp())}:D> (<t:{int(dt.timestamp())}:R>)" if dt else "Unknown"


def server_overview_embed(guild: discord.Guild) -> discord.Embed:
    """Discord information about a server"""
    humans = sum(1 for m in guild.members if not m.bot)
    bots = sum(1 for m in guild.members if m.bot)
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)

    embed = discord.Embed(title=f"🏠 {guild.name}", description=guild.description or None, color=discord.Color.blurple())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    if guild.banner:
        embed.set_image(url=guild.banner.url)

    embed.add_field(
        name="🪪 **General**",
        value=f"**ID:** `{guild.id}`\n**Owner:** {guild.owner.mention if guild.owner else 'Unknown'} (`{guild.owner_id}`)\n**Created:** {fmt_date(guild.created_at)}\n**Roxy joined:** {fmt_date(guild.me.joined_at if guild.me else None)}",
        inline=False
    )
    embed.add_field(
        name="👥 **Members**",
        value=f"**Total:** {guild.member_count:,}\n**Humans:** {humans:,}\n**Bots:** {bots:,}\n**Online:** {online:,}",
        inline=True
    )
    embed.add_field(
        name="💬 **Channels**",
        value=f"**Text:** {len(guild.text_channels)}\n**Voice:** {len(guild.voice_channels)}\n**Categories:** {len(guild.categories)}\n**Forums:** {len(guild.forums)}\n**Stage:** {len(guild.stage_channels)}",
        inline=True
    )
    embed.add_field(
        name="✨ **Extras**",
        value=f"**Roles:** {len(guild.roles) - 1}\n**Emojis:** {len(guild.emojis)}/{guild.emoji_limit}\n**Stickers:** {len(guild.stickers)}/{guild.sticker_limit}\n**Boost tier:** {guild.premium_tier}\n**Boosts:** {guild.premium_subscription_count or 0}",
        inline=True
    )
    embed.add_field(
        name="🔒 **Settings**",
        value=f"**Verification:** {str(guild.verification_level).title()}\n**Content filter:** {str(guild.explicit_content_filter).replace('_', ' ').title()}\n**2FA for mods:** {'Yes' if guild.mfa_level else 'No'}\n**Locale:** {guild.preferred_locale}",
        inline=True
    )
    if guild.features:
        embed.add_field(
            name="🎁 **Features**",
            value=", ".join(f.replace('_', ' ').title() for f in sorted(guild.features))[:1024],
            inline=False
        )
    return embed


def describe_activity(activity) -> str:
    """One readable line for a Discord activity"""
    if isinstance(activity, discord.CustomActivity):
        return " ".join(str(part) for part in ("💭", activity.emoji, activity.name) if part)
    if isinstance(activity, discord.Spotify):
        return f"🎵 Listening to **{activity.title}** by {activity.artist}"
    if isinstance(activity, discord.Streaming):
        return f"📺 Streaming **{activity.name}**"
    if activity.type == discord.ActivityType.playing:
        return f"🎮 Playing **{activity.name}**"
    if activity.type == discord.ActivityType.listening:
        return f"🎧 Listening to **{activity.name}**"
    if activity.type == discord.ActivityType.watching:
        return f"📺 Watching **{activity.name}**"
    if activity.type == discord.ActivityType.competing:
        return f"🏆 Competing in **{activity.name}**"
    return f"• {activity.name}"


CDN = "https://cdn.discordapp.com"


def global_profile_embed(user: discord.User, raw: dict) -> discord.Embed:
    """Discord-wide profile: badges, server tag, avatar, decoration, nameplate, display name style, banner.
    raw is the API user object - newer items (nameplate, name style, tag) aren't in discord.py 2.5 yet."""
    color = user.accent_color or discord.Color.blurple()
    embed = discord.Embed(title=f"🌍 {user.global_name or user.name}", description=f"@{user.name} • `{user.id}`", color=color)
    embed.set_thumbnail(url=user.display_avatar.url)

    nameplate = (raw.get('collectibles') or {}).get('nameplate')
    if user.banner:
        embed.set_image(url=user.banner.url)
    elif nameplate:
        embed.set_image(url=f"{CDN}/assets/collectibles/{nameplate['asset']}static.png")

    badges = [BADGES[flag.name] for flag in user.public_flags.all() if flag.name in BADGES]
    embed.add_field(name="🏅 **Badges**", value="\n".join(badges) or "No public badges", inline=True)

    tag = raw.get('primary_guild') or raw.get('clan')
    if tag and tag.get('identity_enabled') and tag.get('tag'):
        badge_url = f"{CDN}/guild-tag-badges/{tag['identity_guild_id']}/{tag['badge']}.png" if tag.get('badge') else None
        embed.add_field(name="🏷️ **Server Tag**", value=f"**{tag['tag']}**" + (f" • [Badge]({badge_url})" if badge_url else ""), inline=True)

    avatar_kind = "Animated" if user.display_avatar.is_animated() else "Static"
    embed.add_field(name="🖼️ **Avatar**", value=f"{avatar_kind} • [Open]({user.display_avatar.url})", inline=True)

    decoration = raw.get('avatar_decoration_data')
    if decoration:
        decoration_url = f"{CDN}/avatar-decoration-presets/{decoration['asset']}.png?size=240&passthrough=true"
        expires = f" • expires <t:{decoration['expires_at']}:R>" if decoration.get('expires_at') else ""
        embed.add_field(name="✨ **Avatar Decoration**", value=f"[View]({decoration_url}){expires}", inline=True)
    else:
        embed.add_field(name="✨ **Avatar Decoration**", value="None", inline=True)

    if nameplate:
        base = f"{CDN}/assets/collectibles/{nameplate['asset']}"
        embed.add_field(
            name="🪧 **Nameplate**",
            value=f"{nameplate.get('label') or 'Nameplate'}\n**Palette:** {(nameplate.get('palette') or 'default').title()} • [Image]({base}static.png) • [Animated]({base}asset.webm)"[:1024],
            inline=False
        )
    else:
        embed.add_field(name="🪧 **Nameplate**", value="None", inline=True)

    styles = raw.get('display_name_styles')
    if styles:
        colors = " ".join(f"`#{c:06X}`" for c in styles.get('colors') or [])
        embed.add_field(
            name="🔤 **Display Name Style**",
            value=f"**Font:** #{styles.get('font_id')}\n**Effect:** #{styles.get('effect_id')}\n**Colors:** {colors or 'Default'}",
            inline=False
        )
    else:
        embed.add_field(name="🔤 **Display Name Style**", value="Default", inline=True)

    banner_value = f"[Open]({user.banner.url})" if user.banner else "None"
    if user.accent_color:
        banner_value += f" • Color `{user.accent_color}`"
    embed.add_field(name="🎏 **Banner**", value=banner_value, inline=True)
    return embed


def profile_embed(member: discord.Member, user: discord.User = None) -> discord.Embed:
    """Discord profile information for a server member.
    user is the fetched User (only a fetched user carries the banner and accent color)."""
    color = member.color if member.color.value else ((user.accent_color if user else None) or discord.Color.blurple())
    embed = discord.Embed(title=f"👤 {member.display_name}", color=color)
    embed.set_thumbnail(url=member.display_avatar.url)
    if user and user.banner:
        embed.set_image(url=user.banner.url)

    embed.add_field(
        name="🪪 **Account**",
        value=f"**Username:** @{member.name}\n**Display name:** {member.global_name or member.name}\n**ID:** `{member.id}`\n**Type:** {'🤖 Bot' if member.bot else '👤 User'}\n**Created:** {fmt_date(member.created_at)}",
        inline=False
    )

    # Join position among everyone in the server, oldest first
    members_by_join = sorted((m for m in member.guild.members if m.joined_at), key=lambda m: m.joined_at)
    position = next((i for i, m in enumerate(members_by_join, 1) if m.id == member.id), None)
    server_lines = [
        f"**Joined:** {fmt_date(member.joined_at)}",
        f"**Join position:** #{position:,} of {len(members_by_join):,}" if position else None,
        f"**Nickname:** {member.nick}" if member.nick else None,
        f"**Boosting since:** {fmt_date(member.premium_since)}" if member.premium_since else None,
        f"**Timed out until:** {fmt_date(member.timed_out_until)}" if member.is_timed_out() else None,
    ]
    embed.add_field(name=f"🏠 **In {member.guild.name}**", value="\n".join(line for line in server_lines if line), inline=False)

    roles = [role.mention for role in reversed(member.roles) if not role.is_default()]
    if roles:
        roles_text = ""
        for i, role in enumerate(roles):
            if len(roles_text) + len(role) + 2 > 1000:
                roles_text += f"… +{len(roles) - i} more"
                break
            roles_text += role + " "
        embed.add_field(name=f"🎭 **Roles ({len(roles)})**", value=roles_text.strip(), inline=False)

    devices = [name for name, status in (('🖥️ Desktop', member.desktop_status), ('📱 Mobile', member.mobile_status), ('🌐 Web', member.web_status))
               if status != discord.Status.offline]
    status_lines = [STATUS.get(member.status, str(member.status).title()) + (f" on {', '.join(devices)}" if devices else "")]
    status_lines += [describe_activity(activity) for activity in member.activities]
    embed.add_field(name="📡 **Status**", value="\n".join(status_lines)[:1024], inline=False)

    badges = [BADGES[flag.name] for flag in member.public_flags.all() if flag.name in BADGES]
    if badges:
        embed.add_field(name="🏅 **Badges**", value="\n".join(badges), inline=False)

    return embed
