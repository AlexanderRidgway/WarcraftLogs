import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader

load_dotenv()

OFFICER_ROLE_NAME = os.getenv("OFFICER_ROLE_NAME", "Officer")
GUILD_NAME = os.getenv("GUILD_NAME")
GUILD_SERVER = os.getenv("GUILD_SERVER")
GUILD_REGION = os.getenv("GUILD_REGION", "US")
TBC_ZONE_ID = 1007  # The Eye zone — update to current tier as needed


class GuildBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.wcl = WarcraftLogsClient(
            client_id=os.getenv("WARCRAFTLOGS_CLIENT_ID"),
            client_secret=os.getenv("WARCRAFTLOGS_CLIENT_SECRET"),
        )
        self.config = ConfigLoader("config.yaml")

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user}")


bot = GuildBot()


def is_officer(interaction: discord.Interaction) -> bool:
    """Check if the user has the officer role."""
    role_names = [r.name for r in interaction.user.roles]
    return OFFICER_ROLE_NAME in role_names


# Import commands to register them (must come after bot is defined)
from src.commands import topconsistent, player, raidrecap, setconfig  # noqa: E402, F401


def run():
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))


if __name__ == "__main__":
    run()
