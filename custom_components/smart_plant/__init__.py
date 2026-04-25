import logging
import os
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.http import StaticPathConfig
from .const import DOMAIN
# API is handled by coordinator or config flow

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor", "button", "number", "select", "date", "image"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Plant from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register static path for custom images and cards
    static_path = hass.config.path("custom_components/smart_plant/www")
    if not os.path.exists(static_path):
        os.makedirs(static_path, exist_ok=True)
    
    _LOGGER.debug("Registering static path: %s", static_path)
    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig("/smart_plant_static", static_path, False)
        ])
    except Exception as e:
        _LOGGER.error("Error registering static path: %s", e)

    # Register the custom card as a Lovelace resource
    try:
        if "lovelace" in hass.data:
            resources = hass.data["lovelace"].get("resources")
            if resources and hasattr(resources, "async_items"):
                url = "/smart_plant_static/smart-plant-card.js?v=2"
                if not any(res.get("url") == url for res in resources.async_items()):
                    await resources.async_create_item({"res_type": "module", "url": url})
                    _LOGGER.info("Successfully registered Smart Plant Card Lovelace resource")
    except Exception as e:
        _LOGGER.warning("Could not auto-register Lovelace resource: %s", e)

    # Registration of services

    async def handle_upload_image(call):
        """Handle image upload service."""
        entity_ids = call.data.get("entity_id")
        file_path = call.data.get("file_path")
        image_data = call.data.get("image_data")
        
        # We need to find the coordinator for the entity
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, dict): continue # Skip API configs
            if any(entity.entity_id in entity_ids for entity in coordinator.hass.helpers.entity_component.async_get_entities(DOMAIN)):
                if image_data:
                    # Zpracování Base64 dat z karty
                    import base64
                    import uuid
                    header, encoded = image_data.split(",", 1) if "," in image_data else ("", image_data)
                    data = base64.b64decode(encoded)
                    filename = f"custom_upload_{uuid.uuid4().hex[:8]}.jpg"
                    save_path = os.path.join(static_path, filename)
                    
                    def write_file():
                        with open(save_path, "wb") as f:
                            f.write(data)
                    await hass.async_add_executor_job(write_file)
                    
                    # Aktualizace obrázku v konfiguraci
                    await coordinator.async_copy_custom_image(save_path)
                elif file_path:
                    await coordinator.async_copy_custom_image(file_path)

    hass.services.async_register(DOMAIN, "upload_image", handle_upload_image)

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
    if entry.unique_id == "smart_plant_perenual":
        hass.data[DOMAIN].pop("perenual_config", None)
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok
