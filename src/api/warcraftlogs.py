import time
import aiohttp
from typing import Optional

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
API_URL = "https://www.warcraftlogs.com/api/v2/client"


class WarcraftLogsClient:
    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
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
                API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
