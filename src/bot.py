import importlib
import logging
import os
import pathlib
import discord
from discord import app_commands
from dotenv import load_dotenv
from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader

logger = logging.getLogger(__name__)

load_dotenv()

OFFICER_ROLE_NAME = os.getenv("OFFICER_ROLE_NAME", "Officer")
GUILD_NAME = os.getenv("GUILD_NAME")
GUILD_SERVER = os.getenv("GUILD_SERVER")
GUILD_REGION = os.getenv("GUILD_REGION", "US")
TBC_ZONE_ID = 1007  # The Eye zone — update to current tier as needed

_REPO_ROOT = pathlib.Path(__file__).parent.parent


class GuildBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.wcl = WarcraftLogsClient(
            client_id=os.getenv("WARCRAFTLOGS_CLIENT_ID"),
            client_secret=os.getenv("WARCRAFTLOGS_CLIENT_SECRET"),
        )
        self.config = ConfigLoader(str(_REPO_ROOT / "config.yaml"))

    async def setup_hook(self):
        guild_id = os.getenv("DEV_GUILD_ID")
        logger.info("setup_hook: DEV_GUILD_ID=%s, commands registered: %s",
                     guild_id, [c.name for c in self.tree.get_commands()])
        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
            else:
                synced = await self.tree.sync()
            logger.info("Synced %d commands: %s", len(synced), [c.name for c in synced])
        except Exception:
            logger.exception("Failed to sync commands")

    async def on_ready(self):
        logger.info("Logged in as %s", self.user)


bot = GuildBot()


def is_officer(interaction: discord.Interaction) -> bool:
    """Check if the user has the officer role. Returns False in DM context."""
    member = interaction.user
    if not hasattr(member, "roles"):
        return False
    return OFFICER_ROLE_NAME in [r.name for r in member.roles]


# Import command modules to register them with the bot tree.
# Guards against missing modules during incremental development (Tasks 8-11).
_COMMAND_MODULES = ["topconsistent", "player", "raidrecap", "setconfig", "attendance", "setattendance", "gearcheck", "weeklyrecap"]
for _mod in _COMMAND_MODULES:
    try:
        importlib.import_module(f"src.commands.{_mod}")
    except ImportError:
        pass


def run():
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))


if __name__ == "__main__":
    run()
