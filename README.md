# WarcraftLogs Guild Bot

A Discord bot for TBC guild officers to analyze raid performance and identify outstanding raiders for loot priority.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Get WarcraftLogs API credentials: https://www.warcraftlogs.com/api/clients/
3. Create a Discord bot: https://discord.com/developers/applications
4. Copy `.env.example` to `.env` and fill in all values
5. Edit `config.yaml` to configure your specs and utility metrics
6. Run the bot: `python -m src.bot`

## Commands (Officer only)

| Command | Description |
|---|---|
| `/topconsistent [weeks]` | Rank raiders by consistency score |
| `/player <Name-Server>` | Individual parse + utility breakdown |
| `/raidrecap <url>` | Standout performers from a log |
| `/setconfig <spec> <metric> <target>` | Update a metric target |

## Updating Config

Use `/setconfig` in Discord, or edit `config.yaml` directly and restart the bot.

## TBC Zone IDs (for `TBC_ZONE_ID` in bot.py)

- Karazhan: 1002
- Gruul's Lair: 1004
- Magtheridon's Lair: 1005
- Serpentshrine Cavern: 1006
- The Eye: 1007
- Mount Hyjal: 1008
- Black Temple: 1010
- Sunwell Plateau: 1011
