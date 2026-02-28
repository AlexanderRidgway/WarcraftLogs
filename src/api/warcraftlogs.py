import logging
import time
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
DEFAULT_API_URL = "https://www.warcraftlogs.com/api/v2/client"


class WarcraftLogsClient:
    def __init__(self, client_id: str, client_secret: str, api_url: str = DEFAULT_API_URL):
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_url = api_url
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    async def _fetch_token(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                self._token_expiry = time.time() + data["expires_in"] - 60
                return data["access_token"]

    async def _get_token(self) -> str:
        if self._token is None or time.time() >= self._token_expiry:
            self._token = await self._fetch_token()
        return self._token

    async def query(self, graphql_query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query against the WarcraftLogs API."""
        token = await self._get_token()
        payload = {"query": graphql_query}
        if variables is not None:
            payload["variables"] = variables

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._api_url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_guild_roster(self, guild_name: str, server_slug: str, region: str) -> list:
        """Fetch all members of a guild from WarcraftLogs."""
        gql = """
        query($name: String!, $serverSlug: String!, $serverRegion: String!) {
          guildData {
            guild(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
              members {
                data {
                  name
                  classID
                  server { slug region { slug } }
                }
              }
            }
          }
        }
        """
        result = await self.query(gql, {
            "name": guild_name,
            "serverSlug": server_slug,
            "serverRegion": region,
        })
        guild = result["data"]["guildData"]["guild"]
        if guild is None:
            return []
        return guild["members"]["data"]

    async def get_guild_reports(
        self,
        guild_name: str,
        server_slug: str,
        region: str,
        start_time: int,
        end_time: int,
    ) -> list:
        """Fetch all guild reports within a time range, with zone and player data."""
        gql = """
        query($guildName: String!, $guildServerSlug: String!, $guildServerRegion: String!,
              $startTime: Float!, $endTime: Float!) {
          reportData {
            reports(guildName: $guildName, guildServerSlug: $guildServerSlug,
                    guildServerRegion: $guildServerRegion,
                    startTime: $startTime, endTime: $endTime) {
              data {
                code
                startTime
                zone { id name }
                rankedCharacters { name }
              }
            }
          }
        }
        """
        variables = {
            "guildName": guild_name,
            "guildServerSlug": server_slug,
            "guildServerRegion": region,
            "startTime": float(start_time),
            "endTime": float(end_time),
        }
        logger.info("get_guild_reports query: %s", variables)
        result = await self.query(gql, variables)
        logger.info("get_guild_reports response keys: %s", result)
        reports = result["data"]["reportData"]["reports"]
        if reports is None:
            logger.warning("WCL returned null for guild reports (guild=%s, server=%s, region=%s)",
                           guild_name, server_slug, region)
            return []
        reports_data = reports["data"]
        return [
            {
                "code": r["code"],
                "startTime": r["startTime"],
                "zone": r["zone"],
                "players": [c["name"] for c in (r.get("rankedCharacters") or [])],
            }
            for r in reports_data
            if r.get("zone") is not None
        ]

    async def get_character_rankings(
        self, name: str, server_slug: str, region: str, zone_id: int
    ) -> list:
        """Fetch parse percentile rankings per boss for a character."""
        gql = """
        query($name: String!, $serverSlug: String!, $serverRegion: String!, $zoneID: Int!) {
          characterData {
            character(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
              zoneRankings(zoneID: $zoneID) {
                rankings {
                  encounter { name }
                  rankPercent
                  spec
                  class
                }
              }
            }
          }
        }
        """
        variables = {
            "name": name,
            "serverSlug": server_slug,
            "serverRegion": region,
            "zoneID": zone_id,
        }
        result = await self.query(gql, variables)
        logger.info("get_character_rankings(%s, %s, %s, zone=%s) raw response: %s",
                     name, server_slug, region, zone_id, result)
        char = result["data"]["characterData"]["character"]
        if char is None:
            logger.warning("Character not found: %s-%s (%s)", name, server_slug, region)
            return []
        zone = char.get("zoneRankings")
        if zone is None:
            logger.warning("No zoneRankings for %s-%s zone %d: char keys=%s",
                           name, server_slug, zone_id, list(char.keys()))
            return []
        rankings = zone.get("rankings", [])
        if not rankings:
            logger.warning("zoneRankings empty for %s-%s zone %d: zone data=%s",
                           name, server_slug, zone_id, zone)
        return rankings

    @staticmethod
    def _contrib_matches(entry: dict, contrib: dict) -> bool:
        """Return True if a WCL aura/cast entry matches the contribution's spell definition."""
        if "spell_ids" in contrib:
            return entry["id"] in contrib["spell_ids"]
        return entry["id"] == contrib.get("spell_id")

    async def get_utility_data(
        self,
        report_code: str,
        source_id: int,
        start: int,
        end: int,
        contributions: list,
    ) -> dict:
        """
        Fetch utility metrics (uptime % and cast counts) for a player in a report.

        Returns a dict of metric_name -> value.
        """
        uptime_contribs = [c for c in contributions if c["type"] == "uptime"]
        count_contribs = [c for c in contributions if c["type"] == "count"]

        result = {}

        if uptime_contribs:
            debuff_contribs = [c for c in uptime_contribs if c.get("subtype") != "buff"]
            buff_contribs = [c for c in uptime_contribs if c.get("subtype") == "buff"]

            all_auras: list[dict] = []
            total_time = 1

            if debuff_contribs:
                debuff_data = await self._query_table(report_code, source_id, start, end, "Debuffs")
                all_auras += debuff_data.get("auras", [])
                total_time = debuff_data.get("totalTime", 1)

            if buff_contribs:
                buff_data = await self._query_table(report_code, source_id, start, end, "Buffs")
                all_auras += buff_data.get("auras", [])
                if total_time == 1:
                    total_time = buff_data.get("totalTime", 1)

            for contrib in uptime_contribs:
                match = next((a for a in all_auras if self._contrib_matches(a, contrib)), None)
                if match:
                    result[contrib["metric"]] = (match["totalUptime"] / total_time) * 100
                else:
                    result[contrib["metric"]] = 0.0

        if count_contribs:
            cast_data = await self._query_table(report_code, source_id, start, end, "Casts")
            entries = cast_data.get("entries", [])
            for contrib in count_contribs:
                match = next((e for e in entries if self._contrib_matches(e, contrib)), None)
                result[contrib["metric"]] = match["total"] if match else 0

        return result

    async def _query_table(
        self, report_code: str, source_id: int, start: int, end: int, data_type: str
    ) -> dict:
        gql = """
        query($code: String!, $sourceID: Int, $startTime: Float!, $endTime: Float!, $dataType: TableDataType!) {
          reportData {
            report(code: $code) {
              table(sourceID: $sourceID, startTime: $startTime, endTime: $endTime, dataType: $dataType)
            }
          }
        }
        """
        result = await self.query(gql, {
            "code": report_code,
            "sourceID": source_id,
            "startTime": float(start),
            "endTime": float(end),
            "dataType": data_type,
        })
        report = result["data"]["reportData"]["report"]
        if report is None:
            raise ValueError(f"Report '{report_code}' not found on WarcraftLogs")
        table = report.get("table")
        if table is None:
            raise ValueError(f"Table data unavailable for report '{report_code}' (dataType={data_type})")
        return table["data"]

    async def get_report_gear(self, report_code: str) -> list:
        """Fetch gear snapshots for all players in a report from the Summary table."""
        table_data = await self._query_table(report_code, None, 0, 999999999999, "Summary")
        player_details = table_data.get("playerDetails", [])
        return [
            {
                "name": p["name"],
                "gear": p.get("gear", []),
            }
            for p in player_details
        ]

    async def get_report_rankings(self, report_code: str) -> list:
        """Fetch per-player rankings for all fights in a report."""
        gql = """
        query($code: String!) {
          reportData {
            report(code: $code) {
              rankings(playerMetric: default)
            }
          }
        }
        """
        result = await self.query(gql, {"code": report_code})
        report = result["data"]["reportData"]["report"]
        if report is None:
            return []
        rankings_data = report.get("rankings", {})
        if not rankings_data:
            return []
        return rankings_data.get("data", [])

    async def get_report_players(self, report_code: str) -> list:
        """Return all player actors in a report as [{id, name}]."""
        gql = """
        query($code: String!) {
          reportData {
            report(code: $code) {
              masterData {
                actors { id name type }
              }
            }
          }
        }
        """
        result = await self.query(gql, {"code": report_code})
        report = result["data"]["reportData"]["report"]
        if report is None:
            return []
        actors = report.get("masterData", {}).get("actors", [])
        return [{"id": a["id"], "name": a["name"]} for a in actors if a["type"] == "Player"]

    async def get_report_timerange(self, report_code: str) -> dict:
        """Return {start, end} timestamps (relative to report start) for the full report."""
        gql = """
        query($code: String!) {
          reportData {
            report(code: $code) {
              startTime
              endTime
            }
          }
        }
        """
        result = await self.query(gql, {"code": report_code})
        report = result["data"]["reportData"]["report"]
        if report is None:
            return {"start": 0, "end": 0}
        start = int(report["startTime"])
        end = int(report["endTime"])
        return {"start": 0, "end": end - start}
