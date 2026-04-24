"""API client for OpenPlantbook."""
import logging
import aiohttp
import async_timeout

from .const import OPB_BASE_URL, OPB_TOKEN_URL

_LOGGER = logging.getLogger(__name__)

class OpenPlantbookAPI:
    """Client for OpenPlantbook API."""

    def __init__(self, client_id: str, client_secret: str, session: aiohttp.ClientSession):
        """Initialize the API client."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = session
        self.access_token = None

    async def authenticate(self) -> bool:
        """Authenticate with OpenPlantbook."""
        try:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            async with async_timeout.timeout(10):
                response = await self.session.post(OPB_TOKEN_URL, data=data)
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result.get("access_token")
                    return True
                else:
                    _LOGGER.error("Failed to authenticate with OpenPlantbook: %s", response.status)
                    return False
        except Exception as err:
            _LOGGER.error("Error authenticating with OpenPlantbook: %s", err)
            return False

    async def search_plants(self, query: str):
        """Search for plants."""
        if not self.access_token and not await self.authenticate():
            return []

        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"alias": query}
        
        try:
            async with async_timeout.timeout(10):
                response = await self.session.get(f"{OPB_BASE_URL}/plant/search", headers=headers, params=params)
                if response.status == 200:
                    result = await response.json()
                    return result.get("results", [])
                elif response.status == 401:
                    # Token might have expired
                    if await self.authenticate():
                        return await self.search_plants(query)
                return []
        except Exception as err:
            _LOGGER.error("Error searching plants: %s", err)
            return []

    async def get_plant_detail(self, pid: str):
        """Get details for a specific plant."""
        if not self.access_token and not await self.authenticate():
            return None

        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with async_timeout.timeout(10):
                response = await self.session.get(f"{OPB_BASE_URL}/plant/detail/{pid}", headers=headers)
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token might have expired
                    if await self.authenticate():
                        return await self.get_plant_detail(pid)
                return None
        except Exception as err:
            _LOGGER.error("Error getting plant detail for %s: %s", pid, err)
            return None
