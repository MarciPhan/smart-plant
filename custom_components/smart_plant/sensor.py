"""Sensors for Smart Plant."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from .const import DOMAIN
from .entity import SmartPlantEntity

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SmartPlantNextWateringSensor(coordinator, entry),
        SmartPlantCareTipsSensor(coordinator, entry),
        SmartPlantDescriptionSensor(coordinator, entry),
    ])

class SmartPlantNextWateringSensor(SmartPlantEntity, SensorEntity):
    """Sensor for next watering date."""
    _name_suffix = "Next Watering"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the next watering date."""
        return self.coordinator.data.get("next_watering")

    @property
    def extra_state_attributes(self):
        """Return history as attributes."""
        return {
            "watering_history": self.coordinator.data.get("watering_history"),
            "last_watered": self.coordinator.data.get("last_watered"),
        }

class SmartPlantCareTipsSensor(SmartPlantEntity, SensorEntity):
    """Sensor for care tips."""
    _name_suffix = "Care Tips"
    _attr_icon = "mdi:information-outline"

    @property
    def native_value(self):
        """Return a summary of care requirements."""
        d = self.coordinator.details
        tips = []
        
        # Soil Moisture
        if d.get("min_soil_moist"):
            tips.append(f"💧 Min. vlhkost: {d['min_soil_moist']}%")
        
        # Watering intensity
        if d.get("watering"):
            tips.append(f"🚿 Zálivka: {d['watering']}")
            
        # Sunlight
        sun = d.get("sunlight")
        if sun:
            if isinstance(sun, list):
                sun_str = ", ".join(sun)
            else:
                sun_str = str(sun)
            tips.append(f"☀️ Světlo: {sun_str}")
            
        # Temperature
        if d.get("min_temp"):
            tips.append(f"🌡️ Teplota: {d['min_temp']}-{d.get('max_temp', '?')}°C")
            
        return " | ".join(tips) if tips else "Informace o nárocích nejsou k dispozici"

    @property
    def extra_state_attributes(self):
        """Return all details as attributes."""
        attrs = dict(self.coordinator.details)
        attrs["health_history"] = self.coordinator.data.get("health_history")
        return attrs

class SmartPlantDescriptionSensor(SmartPlantEntity, SensorEntity):
    """Sensor for plant description."""
    _name_suffix = "Description"
    _attr_icon = "mdi:text-box-outline"

    @property
    def native_value(self):
        """Return the plant description."""
        return self.coordinator.details.get("description", "Popis není k dispozici")
