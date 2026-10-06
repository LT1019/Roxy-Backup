# Commands

Roxy's prefix is `rr`, with or without a space (`rr help` and `rrhelp` both work). Commands marked **/** are also slash commands.

**Access:** 👤 everyone · 🛡️ server admins (Administrator permission or server owner) in their own server, plus the owner · 👑 bot owner only

## Profiles and stats
| Command | Aliases | Access | What it shows |
|---|---|---|---|
| `rr profile [user]` **/** | `p`, `stats` | 👤 | Full profile with a dropdown of ten views. Looking up people outside the server is 👑 |
| `rr level [user]` | `lvl`, `xp` | 👤 | Level, progress and XP by source |
| `rr games [user]` | `gaming`, `activity` | 👤 | Gaming overview |
| `rr games list [user]` | `favorites`, `fav` | 👤 | All games ranked by playtime |
| `rr games history [user]` | `hist`, `log` | 👤 | Every gaming session, newest first |
| `rr music [user]` | `listening`, `spotify` | 👤 | Listening overview |
| `rr music artists [user]` | `artist`, `fav` | 👤 | Artists ranked by listening time |
| `rr music songs [user]` | `tracks`, `song` | 👤 | Songs ranked by listening time |
| `rr music history [user]` | `hist`, `log` | 👤 | Every listening session, newest first |
| `rr apps [user]` | `app` | 👤 | Time in non-game apps (VS Code, YouTube…) |

## Leaderboards and activity
| Command | Aliases | Access | What it shows |
|---|---|---|---|
| `rr top [category]` | `leaderboard`, `lb` | 👤 | Categories: `messages`, `voice`, `playtime`, `apps`, `listening`, `level`. Pages, a server/global toggle and your rank |
| `rr sessions` | | 👤 | Who's gaming, in voice, using apps or listening right now. 👑 also gets a Global view |

## Info
| Command | Aliases | Access | What it shows |
|---|---|---|---|
| `rr userinfo [user]` **/** | `profileinfo`, `userprofile`, `whois` | 👤 | Discord profile: Server and Global views. 👑 also gets a Servers view and can look up people outside the server |
| `rr serverinfo` | | 👤 | This server's Discord info |
| `rr info` | `about` | 👤 | About Roxy, live counts and supporters |
| `rr invite` | `add` | 👤 | Link to add Roxy to a server |
| `rr ping` | | 👤 | Response time |
| `rr help` | | 👤 | Command center: User / Admin / Owner pages, Detailed / Compact modes |
| `rr ach list` | | 👤 | Every achievement, by category |
| `rr debug [user]` · `rr refresh` | | 👤 | Troubleshoot stats |

## Server admin
| Command | Access | What it does |
|---|---|---|
| `rr welcome` | 🛡️ | Show the welcome message settings |
| `rr welcome message <text>` · `title <text>` | 🛡️ | Set the text or heading. Placeholders: `{user}` `{name}` `{server}` `{members}` |
| `rr welcome channel #channel` | 🛡️ | Where the message is posted |
| `rr welcome on` · `off` · `test` · `reset` | 🛡️ | Turn on or off, preview, back to default |
| `rr announce [#channel] <message>` | 🛡️ | Post an announcement in this server |

## Owner
| Command | What it does |
|---|---|
| `rr addxp <user> <amount>` · `rr setlevel <user> <level>` | Adjust XP or level |
| `rr resetuser <user>` · `rr deleteuser <user or ID>` | Reset stats, or erase all data for a deletion request |
| `rr forceupdate <user>` | Recalculate totals from sessions |
| `rr ach users\|give\|remove` · `rr giveach` · `rr removeach` | Manage granted achievements |
| `/dbstats` · `/logs` | Database stats with Excel export, and recent logs (only the owner sees them) |
| `rr totalstats` · `rr serverlist` · `rr serverstats [server ID]` | Global statistics, every server, one server in detail |
| `rr cleanup` · `rr backup` | Remove inactive users, back up the database |
| `rr setstatus <text\|clear>` · `rr presence [user]` | Bot status, and what Discord shares about a member |
| `rr clearsessions` · `rr reload` · `rr shutdown` | End sessions, hot-reload code, save and shut down |
