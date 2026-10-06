# Case Study: Roxy, a Discord Stats Bot

**Role:** Developer and owner · **Timeline:** June 2025 – present · **Stack:** Python 3.13, discord.py 2.5, SQLite (aiosqlite)

## At a glance

| | |
|---|---|
| **What** | A Discord bot that turns chat, voice, gaming, app and Spotify activity into XP, levels, profiles and leaderboards |
| **Scale** | 23 servers · 1,600+ members · 258 tracked users · 21,000+ recorded sessions |
| **Biggest challenge** | Leaderboards built on bad data: stuck sessions had added tens of thousands of hours that never happened |
| **Outcome** | Trustworthy stats, an anti-spam XP system, a role and permission model, and a bot that recovers from crashes on its own |

---

## 1. The problem

Discord already shows what people are doing: the game they're playing, the song on Spotify, whether they're in a voice call. It doesn't remember any of it. Server communities wanted to know who the most active members are, how many hours someone has put into a game, and what everyone listens to.

Most levelling bots only count messages, and music-stats bots make every member create and link a Last.fm account. I wanted one bot that tracks **all** activity automatically, with nothing for members to set up.

## 2. Where the first version stood

The first version worked on the surface, but a review turned up problems in four areas:

| Area | Problem |
|---|---|
| **Data** | A session that never received an "ended" event kept running. Some sessions lasted for **months**. |
| **Data** | Two copies of the bot were running at once, so sessions were recorded **twice** and every command got **two replies**. |
| **Security** | The admin menu's buttons worked for anyone who clicked them, and a test command let anyone award themselves XP. |
| **Honesty** | The help menu advertised admin commands that didn't exist. |
| **Privacy** | Message contents were printed to the console log. |
| **XP** | Every message gave 5 XP, so spamming was the fastest way up the leaderboard. |

## 3. What I did

### 3.1 Fixing the data, and then the tracking
The leaderboards were the core of the bot, and they weren't true. Before touching anything, I measured the damage on a **copy** of the database:

- **269 duplicate sessions**, the same session recorded twice, a few milliseconds apart
- Sessions far longer than humanly possible, adding **tens of thousands of hours**
- **876 sessions** of apps like Visual Studio Code, YouTube and Netflix counted as *games*

Then the cleanup ran in one locked database transaction, after a full backup and a dry run:

| | Before | After |
|---|---|---|
| Total gaming time | 12,956 h | 1,291 h |
| Total XP across users | 807,947 | 101,838 |
| Highest level | 85 | 12 |

Fixing the data alone wasn't enough; I fixed the causes too:
- **A 24-hour cap** on any single session
- **Crash recovery:** sessions left open by a crash are discarded at startup, because their real end time is unknown. Members who are still playing or in a call are picked up again when the bot reconnects.
- **De-duplicated events:** Discord sends one presence update **per shared server**, so a member in five servers with the bot triggers five events. Comparing against the bot's own in-memory state, and updating that state *before* any `await`, means only the first event starts a session.
- **A single-instance lock**, so a second copy of the bot refuses to start. This ended the double replies for good.
- **Apps kept apart from games:** non-game apps became their own category instead of being thrown away, and their sessions were restored from the backup.

### 3.2 An XP system that rewards real activity
| Activity | XP | Anti-abuse rule |
|---|---|---|
| Messages | 5 per minute | Only the first message in each minute earns XP |
| Voice | 25 per active minute | No XP when alone, muted, deafened or in the AFK channel |
| Gaming / apps | 1 per minute | 24-hour session cap |
| Listening | 1 per 2 minutes | 24-hour session cap |

Voice XP is checked **every minute** while a call is going, instead of in one lump when someone leaves. That makes it fair and lets levels rise during a call. Levels grow progressively: level *N* needs `(N − 1) × N × 50` total XP.

### 3.3 Security and permissions
I replaced the single hidden "admin" check with three roles:

| Role | Who | Can do |
|---|---|---|
| 👤 User | everyone | profiles, leaderboards, info |
| 🛡️ Server Admin | members with Administrator, plus the server owner | welcome message and announcements, **in their own server only** |
| 👑 Owner | the bot owner | user management, database tools, cross-server views |

- **Every menu checks who pressed it,** so nobody can use someone else's menu.
- **Owner-only commands stay silent** for everyone else, which doesn't reveal that they exist.
- **The private data tools** (database stats and logs) are slash commands that only the owner can see ("Only you can see this").

### 3.4 Privacy
- Message **content is never stored or logged**; the bot only counts messages.
- I wrote a public **Privacy Policy** and **Terms of Service**, which Discord requires for bot verification.
- Data deletion on request, for one user or completely.
- The owner's Excel export protects against spreadsheet **formula injection** and keeps 18-digit Discord IDs exact, which spreadsheets would otherwise round.

### 3.5 Making it usable
I moved commands from walls of text to Discord's interactive components:
- **Profiles** with ten views (overview, level, gaming, apps, music, favourites, history)
- **Leaderboards** with six categories, pages, and server or global scope
- **A help menu** with User, Admin and Owner pages, plus Detailed and Compact modes
- **Close buttons** that delete the menu instead of leaving clutter behind

Long lists respect Discord's limits (1,024 characters per field, 4,096 per description). Names are escaped, so a username with `_` or `*` can't break the formatting.

### 3.6 Running it 24/7
- A start script that **restarts the bot after a crash** and rotates the log file
- **Auto-start** with Windows, plus a hidden launcher so no console window stays open
- A **safe shutdown** that ends and saves every active session first
- A **hot reload** that also reloads the shared modules, so most updates don't need a restart

## 4. Results
- **Stats people can trust.** Leaderboards now reflect real activity, which is the whole point of a stats bot.
- **No more spam farming.** The XP rules reward conversation and time, not message count.
- **Server owners have a say:** admins customise their welcome message without needing the bot owner.
- **Ready to grow:** an invite link, a support server, Patreon supporter perks, and the Discord verification checklist completed apart from identity verification.

## 5. What I learned
- **Measure before you fix.** Running the cleanup on a copy first, with dry runs and backups, made a risky change to live data safe and reversible.
- **Fix the cause, not just the symptom.** Cleaning the data once would have been undone within weeks without the session cap, the crash recovery and the single-instance lock.
- **Distributed events are tricky even in a small bot.** The duplicate presence events looked like random bugs until I understood that Discord sends one per shared server.
- **Privacy is part of the design.** Deciding early to count messages instead of storing them made the privacy policy simple and verification easier.

## 6. What's next
- **Per-server settings:** level-up messages on or off, a level-up channel, and channels that give no XP
- **Role rewards:** automatic roles at chosen levels
- **Cloud hosting,** so uptime doesn't depend on one PC
- **Splitting the largest modules** and adding automated tests
