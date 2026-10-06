# Setup and Operations

## 1. Create the Discord application
1. In the [Discord Developer Portal](https://discord.com/developers/applications), create an application and add a bot.
2. Under **Bot → Privileged Gateway Intents**, enable **Presence**, **Server Members** and **Message Content**. Roxy needs them to track activity and count messages.
3. Under **Installation**, give the guild install the `bot` and `applications.commands` scopes with these permissions: View Channels, Send Messages, Send Messages in Threads, Embed Links, Attach Files, Read Message History, Use External Emojis and Manage Messages. Administrator isn't needed.

## 2. Install
```bash
python -m venv roxy_env
roxy_env\Scripts\activate          # Windows (macOS/Linux: source roxy_env/bin/activate)
pip install -r requirements.txt
```

## 3. Configure
Copy `.env.example` to `.env` and fill it in. Never commit `.env`; `.gitignore` already excludes it.

| Variable | Required | Purpose |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | The bot token |
| `ADMIN_USER_ID` | ✅ | Your Discord user ID; this account becomes the bot owner |
| `INVITE_URL` · `SUPPORT_SERVER_URL` · `PATREON_URL` · `KOFI_URL` | | Link buttons under `rr help` and `rr info`. Unset ones are hidden |
| `PATRON_GUILD_ID` · `PATREON_ROLE_*` | | Server and role names for supporter perks |
| `APP_ACTIVITIES` | | Extra app names to track as apps instead of games (comma-separated) |

## 4. Run
```bash
python roxy.py
```
On startup the console shows the slash commands being synced, the number of servers, and how many sessions were picked up. Type `rr help` in a server to check that Roxy answers.

## Running 24/7 on Windows
| File | Purpose |
|---|---|
| `start_roxy.bat` | Runs Roxy and restarts it 15 seconds after a crash. Stops for good after `rr shutdown`, a bad token, or if Roxy is already running. Logs to `logs/roxy.log`, rotated past 5 MB |
| `start_roxy_hidden.vbs` | Starts the script above without a console window. A shortcut in the Windows Startup folder starts Roxy at login |
| `stop_roxy.bat` | Stops the background copy |

Only one copy can run at a time. A second copy exits immediately instead of connecting, which prevents double replies.

## Updating
| Change | How to apply |
|---|---|
| Cogs, `database.py`, `config.py`, `info_embeds.py`, `patreon.py` | `rr reload` in Discord |
| `roxy.py` (events, help menu, background tasks) | `rr shutdown`, then start again |

`rr shutdown` saves every active session first, so nobody loses tracked time.

## Data and backups
- **Database:** `data/roxy.db` (SQLite). The whole `data/` folder is excluded from git, because it contains user data.
- **Backups:** `rr backup` makes a consistent copy while Roxy is running, using SQLite's online backup.
- **Deletion requests:** `rr deleteuser <user or ID>` removes everything stored about a person.
- **Schema changes** are applied automatically at startup.

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Every command answers twice | Two copies running, e.g. one in a terminal and one in the background |
| Someone's games or Spotify aren't tracked | Their Discord activity privacy hides it. `rr presence <user>` shows what Discord shares |
| Slash commands missing | They can take a few minutes to appear after a restart; Ctrl+R refreshes Discord |
| Roxy offline | Check `logs/roxy.log`; an invalid token stops the restart loop |
