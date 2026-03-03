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

    async def get_game_classes(self) -> dict[int, str]:
        """Fetch class ID -> name mapping from WCL gameData."""
        gql = """
        query {
          gameData {
            classes {
              id
              name
            }
          }
        }
        """
        result = await self.query(gql, {})
        classes = result["data"]["gameData"]["classes"]
        return {c["id"]: c["name"].lower() for c in classes}

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
        results = await self.get_character_rankings_batch(
            [(name, server_slug, region)], zone_id
        )
        return results.get(name, [])

    async def get_character_rankings_batch(
        self, characters: list[tuple[str, str, str]], zone_id: int
    ) -> dict[str, list]:
        """Fetch rankings for multiple characters in a single GraphQL query.

        characters: list of (name, server_slug, region) tuples
        Returns: dict of character_name -> list of ranking entries
        """
        if not characters:
            return {}

        # Build a batched query using GraphQL aliases
        alias_parts = []
        for i, (name, server_slug, region) in enumerate(characters):
            # Sanitize name for use as GraphQL alias (alphanumeric only)
            alias = f"char{i}"
            alias_parts.append(
                f'{alias}: character(name: "{name}", serverSlug: "{server_slug}", '
                f'serverRegion: "{region}") {{ zoneRankings(zoneID: {zone_id}) }}'
            )

        gql = "query { characterData { " + " ".join(alias_parts) + " } }"
        result = await self.query(gql)
        if "errors" in result:
            logger.warning("get_character_rankings_batch GraphQL errors: %s", result["errors"])
            return {}

        char_data = result.get("data", {}).get("characterData", {})
        output = {}
        for i, (name, _, _) in enumerate(characters):
            alias = f"char{i}"
            char = char_data.get(alias)
            if char is None:
                continue
            zone = char.get("zoneRankings")
            if zone is None:
                continue
            rankings = zone.get("rankings", [])
            if rankings:
                output[name] = rankings
        return output

    @staticmethod
    def _contrib_matches(entry: dict, contrib: dict) -> bool:
        """Return True if a WCL aura/cast entry matches the contribution's spell definition."""
        spell_id = entry.get("guid") or entry.get("id")
        if "spell_ids" in contrib:
            return spell_id in contrib["spell_ids"]
        return spell_id == contrib.get("spell_id")

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
                # Enemy debuffs (Expose Armor, Sunder, etc.) must use hostilityType=Enemies
                # and no sourceID — WCL's Debuffs table with sourceID returns debuffs ON the
                # player, not debuffs applied BY the player to enemies.
                debuff_data = await self._query_table(
                    report_code, None, start, end, "Debuffs",
                    hostility_type="Enemies",
                )
                all_auras += debuff_data.get("auras", [])
                total_time = debuff_data.get("totalTime", 1)

            if buff_contribs:
                buff_data = await self._query_table(report_code, source_id, start, end, "Buffs")
                all_auras += buff_data.get("auras", [])
                if total_time == 1:
                    total_time = buff_data.get("totalTime", 1)

            for contrib in uptime_contribs:
                matches = [a for a in all_auras if self._contrib_matches(a, contrib)]
                if matches:
                    best = max(m["totalUptime"] for m in matches)
                    result[contrib["metric"]] = (best / total_time) * 100
                else:
                    result[contrib["metric"]] = 0.0

        if count_contribs:
            cast_data = await self._query_table(report_code, source_id, start, end, "Casts")
            entries = cast_data.get("entries", [])
            for contrib in count_contribs:
                total = sum(e["total"] for e in entries if self._contrib_matches(e, contrib))
                result[contrib["metric"]] = total

        return result

    async def check_combo_presence(
        self,
        report_code: str,
        source_id: int,
        start: int,
        end: int,
        contrib: dict,
    ) -> float:
        """Check if a player has either a Flask OR (Battle Elixir + Guardian Elixir).

        Returns 100.0 if present, 0.0 if not.
        """
        buff_data = await self._query_table(report_code, source_id, start, end, "Buffs")
        auras = buff_data.get("auras", [])

        def _has_any(ids: list[int]) -> bool:
            return any(
                (a.get("guid") or a.get("id")) in ids and a.get("totalUptime", 0) > 0
                for a in auras
            )

        # Check flasks first
        if _has_any(contrib.get("flask_ids", [])):
            return 100.0

        # Check battle + guardian elixir combo
        has_battle = _has_any(contrib.get("battle_elixir_ids", []))
        has_guardian = _has_any(contrib.get("guardian_elixir_ids", []))
        if has_battle and has_guardian:
            return 100.0

        return 0.0

    async def _query_table(
        self, report_code: str, source_id: int, start: int, end: int, data_type: str,
        hostility_type: str | None = None,
    ) -> dict:
        if hostility_type:
            gql = """
            query($code: String!, $sourceID: Int, $startTime: Float!, $endTime: Float!,
                  $dataType: TableDataType!, $hostilityType: HostilityType!) {
              reportData {
                report(code: $code) {
                  table(sourceID: $sourceID, startTime: $startTime, endTime: $endTime,
                        dataType: $dataType, hostilityType: $hostilityType)
                }
              }
            }
            """
            variables = {
                "code": report_code,
                "sourceID": source_id,
                "startTime": float(start),
                "endTime": float(end),
                "dataType": data_type,
                "hostilityType": hostility_type,
            }
        else:
            gql = """
            query($code: String!, $sourceID: Int, $startTime: Float!, $endTime: Float!, $dataType: TableDataType!) {
              reportData {
                report(code: $code) {
                  table(sourceID: $sourceID, startTime: $startTime, endTime: $endTime, dataType: $dataType)
                }
              }
            }
            """
            variables = {
                "code": report_code,
                "sourceID": source_id,
                "startTime": float(start),
                "endTime": float(end),
                "dataType": data_type,
            }
        result = await self.query(gql, variables)
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
        player_details = table_data.get("playerDetails", {})
        # playerDetails is grouped by role: {healers: [...], tanks: [...], dps: [...]}
        all_players = []
        if isinstance(player_details, dict):
            for role_players in player_details.values():
                if isinstance(role_players, list):
                    all_players.extend(role_players)
        elif isinstance(player_details, list):
            all_players = player_details
        result = []
        for p in all_players:
            ci = p.get("combatantInfo", {})
            gear = ci.get("gear", []) if isinstance(ci, dict) else []
            result.append({"name": p["name"], "gear": gear})
        return result

    async def get_report_player_specs(self, report_code: str) -> dict[str, str]:
        """Return a mapping of player name -> spec name from the Summary table.

        The Summary table's playerDetails groups players by role (tanks, healers, dps)
        and each player entry has a 'type' (class) and 'specs' array. This is more
        reliable than the rankings endpoint for class/spec identification.
        """
        try:
            table_data = await self._query_table(report_code, None, 0, 999999999999, "Summary")
        except Exception:
            logger.warning("Failed to fetch Summary table for specs in %s", report_code)
            return {}
        player_details = table_data.get("playerDetails", {})
        all_players = []
        if isinstance(player_details, dict):
            for role_players in player_details.values():
                if isinstance(role_players, list):
                    all_players.extend(role_players)
        elif isinstance(player_details, list):
            all_players = player_details

        spec_map: dict[str, str] = {}
        for p in all_players:
            if not isinstance(p, dict):
                continue
            name = p.get("name", "")
            if not name:
                continue
            # 'type' field is the class name (e.g., "Warlock")
            cls = p.get("type", "")
            # 'specs' can be a list of spec objects or strings
            specs = p.get("specs", [])
            spec_name = ""
            if specs and isinstance(specs, list):
                first = specs[0]
                if isinstance(first, dict):
                    spec_name = first.get("spec", "")
                elif isinstance(first, str):
                    spec_name = first
            if cls and spec_name:
                spec_map[name] = f"{cls}:{spec_name}"
            elif cls:
                spec_map[name] = cls
            logger.debug("Player spec: %s -> class=%s spec=%s raw_specs=%s", name, cls, spec_name, specs)
        return spec_map

    async def get_report_rankings(self, report_code: str) -> list:
        """Fetch per-player rankings for all fights in a report.

        Returns one entry per player with their average rankPercent
        across all boss fights: {name, class, spec, rankPercent}.

        Uses two queries via GraphQL aliases — dps metric for DPS/tanks,
        hps metric for healers — so each role gets the correct parse.
        """
        gql = """
        query($code: String!) {
          reportData {
            report(code: $code) {
              dpsRankings: rankings(playerMetric: dps)
              hpsRankings: rankings(playerMetric: hps)
            }
          }
        }
        """
        result = await self.query(gql, {"code": report_code})
        report = result["data"]["reportData"]["report"]
        if report is None:
            return []

        dps_data = report.get("dpsRankings", {})
        hps_data = report.get("hpsRankings", {})

        # Collect per-fight parses per player, then average
        player_parses: dict[str, list[float]] = {}
        player_info: dict[str, dict] = {}
        per_fight: list[dict] = []

        def _process_chars(characters, encounter_name):
            for char in characters:
                name = char.get("name", "Unknown")
                rank_pct = char.get("rankPercent") or 0
                player_parses.setdefault(name, []).append(rank_pct)
                if name not in player_info:
                    player_info[name] = {
                        "class": char.get("class") or "",
                        "spec": char.get("spec") or "",
                    }
                per_fight.append({
                    "name": name,
                    "encounter_name": encounter_name,
                    "rankPercent": rank_pct,
                })

        # DPS rankings: use for dps and tanks roles
        for fight in (dps_data.get("data") or []):
            enc_name = fight.get("encounter", {}).get("name", "Unknown")
            roles = fight.get("roles", {})
            for role_name, role_data in roles.items():
                if not isinstance(role_data, dict):
                    continue
                if role_name == "healers":
                    continue
                _process_chars(role_data.get("characters", []), enc_name)

        # HPS rankings: use for healers role only
        for fight in (hps_data.get("data") or []):
            enc_name = fight.get("encounter", {}).get("name", "Unknown")
            roles = fight.get("roles", {})
            healers = roles.get("healers")
            if not isinstance(healers, dict):
                continue
            _process_chars(healers.get("characters", []), enc_name)

        averages = [
            {
                "name": name,
                "class": player_info[name]["class"],
                "spec": player_info[name]["spec"],
                "rankPercent": sum(parses) / len(parses),
            }
            for name, parses in player_parses.items()
        ]
        return averages, per_fight

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

    async def get_report_fights(self, report_code: str) -> list:
        """Fetch all boss fights for a report (excludes trash)."""
        gql = """
        query($code: String!) {
          reportData {
            report(code: $code) {
              fights(killType: Encounters) {
                id
                name
                kill
                startTime
                endTime
                fightPercentage
                encounterID
              }
            }
          }
        }
        """
        result = await self.query(gql, {"code": report_code})
        report = result.get("data", {}).get("reportData", {}).get("report")
        if not report:
            return []
        return report.get("fights", [])

    async def get_report_deaths(self, report_code: str, start: float, end: float) -> list:
        """Fetch death events for a time window. Returns list of death entries."""
        data = await self._query_table(report_code, None, start, end, "Deaths")
        return data.get("entries", [])

    async def get_fight_stats(self, report_code: str, start: float, end: float) -> dict:
        """Fetch per-player damage and healing for a fight time window.

        Returns: {player_name: {damage_done, healing_done, dps, hps}}
        """
        duration_s = (end - start) / 1000.0
        if duration_s <= 0:
            return {}

        dmg_data = await self._query_table(report_code, None, start, end, "DamageDone")
        heal_data = await self._query_table(report_code, None, start, end, "Healing")

        # WCL table entries use class name as "type" (e.g. "Shaman", "Warrior"),
        # not "Player". Exclude known non-player types instead.
        NON_PLAYER_TYPES = {"Pet", "NPC", "Boss", "Unknown"}

        stats = {}
        for entry in dmg_data.get("entries", []):
            if entry.get("type") in NON_PLAYER_TYPES:
                continue
            name = entry["name"]
            total = entry.get("total", 0)
            stats[name] = {
                "damage_done": total,
                "dps": round(total / duration_s, 1) if duration_s > 0 else 0,
                "healing_done": 0,
                "hps": 0,
            }

        for entry in heal_data.get("entries", []):
            if entry.get("type") in NON_PLAYER_TYPES:
                continue
            name = entry["name"]
            total = entry.get("total", 0)
            if name not in stats:
                stats[name] = {"damage_done": 0, "dps": 0, "healing_done": 0, "hps": 0}
            stats[name]["healing_done"] = total
            stats[name]["hps"] = round(total / duration_s, 1) if duration_s > 0 else 0

        return stats

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
