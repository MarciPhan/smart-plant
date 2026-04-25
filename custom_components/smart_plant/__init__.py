import logging
import os
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.http import StaticPathConfig
from .const import DOMAIN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from .api import OpenPlantbookAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor", "button", "number", "select", "date", "image"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Plant from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register static path for custom images
    static_path = hass.config.path("custom_components/smart_plant/www")
    if not os.path.exists(static_path):
        os.makedirs(static_path, exist_ok=True)
    
    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig("/smart_plant_static", static_path, False)
        ])
    except Exception:
        pass

    async def handle_search(call):
        """Handle the search service call."""
        query = call.data.get("query")
        api_config = hass.data[DOMAIN].get("api_config")
        if not api_config:
            _LOGGER.error("Smart Plant API not configured")
            return
        
        session = async_get_clientsession(hass)
        api = OpenPlantbookAPI(api_config[CONF_CLIENT_ID], api_config[CONF_CLIENT_SECRET], session)
        results = await api.search_plants(query)
        
        hass.bus.async_fire("smart_plant_search_results", {"query": query, "results": results})

    hass.services.async_register(DOMAIN, "search_plants", handle_search)

    async def handle_upload_image(call):
        """Handle image upload service."""
        entity_ids = call.data.get("entity_id")
        file_path = call.data.get("file_path")
        
        # We need to find the coordinator for the entity
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, dict): continue # Skip API configs
            if any(entity.entity_id in entity_ids for entity in coordinator.hass.helpers.entity_component.async_get_entities(DOMAIN)):
                await coordinator.async_copy_custom_image(file_path)

    hass.services.async_register(DOMAIN, "upload_image", handle_upload_image)

    if entry.unique_id == "smart_plant_api":
        # This is the global OpenPlantbook API configuration
        hass.data[DOMAIN]["api_config"] = entry.data
        return True

    if entry.unique_id == "smart_plant_perenual":
        # This is the Perenual API configuration
        hass.data[DOMAIN]["perenual_config"] = entry.data
        return True

    # This is an individual plant
    from .coordinator import SmartPlantCoordinator
    coordinator = SmartPlantCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.unique_id == "smart_plant_api":
        hass.data[DOMAIN].pop("api_config", None)
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok
