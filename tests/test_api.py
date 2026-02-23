import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.warcraftlogs import WarcraftLogsClient

@pytest.mark.asyncio
async def test_get_access_token():
    client = WarcraftLogsClient(client_id="test_id", client_secret="test_secret")

    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"access_token": "abc123", "expires_in": 3600})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.post", return_value=mock_response):
        token = await client._fetch_token()

    assert token == "abc123"


@pytest.mark.asyncio
async def test_token_cached_until_expiry():
    client = WarcraftLogsClient(client_id="test_id", client_secret="test_secret")
    client._token = "cached_token"
    client._token_expiry = float("inf")

    token = await client._get_token()
    assert token == "cached_token"
