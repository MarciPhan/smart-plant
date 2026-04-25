import logging
import asyncio
import aiohttp

from .const import (
    OPB_BASE_URL, 
    OPB_TOKEN_URL, 
    WIKI_SEARCH_URL, 
    WIKI_SUMMARY_URL, 
    MOISTURE_HEURISTICS,
    PERENUAL_BASE_URL,
    PERENUAL_WATERING_MAPPING
)

_LOGGER = logging.getLogger(__name__)

class PerenualAPI:
    """Client for Perenual API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession):
        """Initialize."""
        self.api_key = api_key
        self.session = session

    async def search_plants(self, query: str):
        """Search for plants on Perenual."""
        url = f"{PERENUAL_BASE_URL}/species-list"
        params = {
            "key": self.api_key,
            "q": query
        }
        try:
            async with asyncio.timeout(10):
                response = await self.session.get(url, params=params)
                if response.status == 200:
                    result = await response.json()
                    # Perenual returns {"data": [...]}
                    plants = result.get("data", [])
                    return [{"pid": str(p["id"]), "alias": p["common_name"], "display_pid": p["scientific_name"][0], "source": "perenual"} for p in plants if "id" in p]
                return []
        except Exception as err:
            _LOGGER.error("Error searching Perenual: %s", err)
            return []

    async def get_plant_detail(self, plant_id: str):
        """Get details for a specific plant from Perenual."""
        url = f"{PERENUAL_BASE_URL}/species/details/{plant_id}"
        params = {"key": self.api_key}
        try:
            async with asyncio.timeout(10):
                response = await self.session.get(url, params=params)
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract watering
                    watering = data.get("watering", "").lower()
                    min_moist = PERENUAL_WATERING_MAPPING.get(watering, 30)
                    
                    return {
                        "pid": plant_id,
                        "display_pid": data.get("scientific_name", [plant_id])[0],
                        "description": data.get("description", ""),
                        "image_url": data.get("default_image", {}).get("regular_url"),
                        "min_soil_moist": min_moist,
                        "watering": watering,
                        "sunlight": data.get("sunlight", []),
                        "source": "perenual"
                    }
                return None
        except Exception as err:
            _LOGGER.error("Error getting Perenual detail for %s: %s", plant_id, err)
            return None

class WikipediaAPI:
    """Client for Wikipedia API."""

    def __init__(self, session: aiohttp.ClientSession, lang: str = "en"):
        """Initialize."""
        self.session = session
        self.lang = lang
        self.search_url = f"https://{lang}.wikipedia.org/w/api.php"
        self.summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"

    async def search_plants(self, query: str):
        """Search for plants on Wikipedia."""
        params = {
            "action": "opensearch",
            "search": query,
            "limit": 10,
            "namespace": 0,
            "format": "json"
        }
        try:
            async with asyncio.timeout(10):
                response = await self.session.get(self.search_url, params=params)
                if response.status == 200:
                    result = await response.json()
                    # OpenSearch returns [query, titles, summaries, links]
                    titles = result[1]
                    return [{"pid": t, "alias": t, "display_pid": t, "source": "wikipedia"} for t in titles]
                return []
        except Exception as err:
            _LOGGER.error("Error searching Wikipedia (%s): %s", self.lang, err)
            return []

    async def get_plant_detail(self, title: str):
        """Get details for a specific plant from Wikipedia."""
        url = f"{self.summary_url}{title.replace(' ', '_')}"
        try:
            async with asyncio.timeout(10):
                response = await self.session.get(url)
                if response.status == 200:
                    data = await response.json()
                    extract = data.get("extract", "")
                    
                    # Heuristic care analysis
                    min_moist = self._heuristic_analysis(extract)
                    
                    return {
                        "pid": title,
                        "display_pid": title,
                        "description": extract,
                        "image_url": data.get("thumbnail", {}).get("source"),
                        "min_soil_moist": min_moist,
                        "source": "wikipedia"
                    }
                return None
        except Exception as err:
            _LOGGER.error("Error getting Wikipedia detail for %s: %s", title, err)
            return None

    def _heuristic_analysis(self, text: str) -> int:
        """Estimate moisture needs from text."""
        text = text.lower()
        score = 30 # Default medium
        matches = 0
        
        for keyword, value in MOISTURE_HEURISTICS.items():
            if keyword in text:
                score += value
                matches += 1
                
        if matches > 0:
            return round(score / (matches + 1)) # Weighted average with default
            
        return 30

class OpenPlantbookAPI:
    """Client for OpenPlantbook API."""

    def __init__(self, client_id: str, client_secret: str, session: aiohttp.ClientSession):
        """Initialize the API client."""
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.session = session
        self.access_token = None

    async def authenticate(self) -> bool:
        """Authenticate with OpenPlantbook."""
        if not self.client_id or not self.client_secret:
            _LOGGER.debug("No API credentials provided, skipping authentication")
            return False
            
        _LOGGER.debug("Attempting to authenticate with OpenPlantbook at %s", OPB_TOKEN_URL)
        try:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            async with asyncio.timeout(10):
                response = await self.session.post(OPB_TOKEN_URL, data=data)
                _LOGGER.debug("OPB auth response status: %s", response.status)
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result.get("access_token")
                    _LOGGER.debug("Successfully authenticated with OpenPlantbook")
                    return True
                else:
                    text = await response.text()
                    _LOGGER.error("Failed to authenticate with OpenPlantbook: %s - %s", response.status, text)
                    return False
        except Exception as err:
            _LOGGER.exception("Error authenticating with OpenPlantbook: %s", err)
            return False

    async def search_plants(self, query: str):
        """Search for plants."""
        if not self.access_token and not await self.authenticate():
            return []

        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"alias": query}
        
        try:
            async with asyncio.timeout(10):
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
            async with asyncio.timeout(10):
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
