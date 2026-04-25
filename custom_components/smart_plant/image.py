"""Images for Smart Plant."""
import aiohttp
from homeassistant.components.image import ImageEntity
from .const import DOMAIN
from .entity import SmartPlantEntity

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up images."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SmartPlantImage(coordinator, entry),
    ])

class SmartPlantImage(SmartPlantEntity, ImageEntity):
    """Image entity for the plant picture."""
    _name_suffix = "Picture"

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator, entry)
        ImageEntity.__init__(self, coordinator.hass)
        self._image_url = coordinator.details.get("image_url")

    @property
    def entity_picture(self):
        """Return the entity picture."""
        if self.coordinator.custom_image_url:
            return self.coordinator.custom_image_url
        return self.coordinator.details.get("image_url")

    @property
    def image_url(self):
        """Return the image URL."""
        if self.coordinator.custom_image_url:
            return self.coordinator.custom_image_url
        return self.coordinator.details.get("image_url")

    async def async_image(self):
        """Return bytes of the image."""
        url = self.image_url
        if not url:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
        except Exception:
            return None
        return None
