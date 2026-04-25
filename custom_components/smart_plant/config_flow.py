"""Config flow for Smart Plant integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import os
import json
from .const import (
    DOMAIN, 
    CONF_CLIENT_ID, 
    CONF_CLIENT_SECRET, 
    CONF_PERENUAL_KEY,
    ATTR_SPECIES, 
    ATTR_PID, 
    DEFAULT_DAYS_BETWEEN_WATERINGS
)
from .api import WikipediaAPI, OpenPlantbookAPI, PerenualAPI

class SmartPlantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Plant."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self._plant_name = None
        self._search_results = []
        self._selected_source = "wikipedia"

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            self._selected_source = user_input["source"]
            
            if self._selected_source == "perenual":
                entries = self._async_current_entries()
                if not any(entry.unique_id == "smart_plant_perenual" for entry in entries):
                    return await self.async_step_perenual_setup()
            
            return await self.async_step_plant_setup()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("source", default="wikipedia"): vol.In({
                    "wikipedia": "Wikipedia (Public, No Key)",
                    "perenual": "Perenual (Professional, Key Required)",
                    "local": "Local Database (Bundled - No Key)"
                }),
            }),
        )

    async def async_step_perenual_setup(self, user_input=None):
        """Setup Perenual API key."""
        errors = {}
        if user_input is not None:
            api_key = user_input[CONF_PERENUAL_KEY]
            session = async_get_clientsession(self.hass)
            api = PerenualAPI(api_key, session)
            
            if await api.search_plants("Monstera"):
                await self.async_set_unique_id("smart_plant_perenual")
                return self.async_create_entry(
                    title="Perenual API Settings",
                    data={CONF_PERENUAL_KEY: api_key}
                )
            else:
                errors["base"] = "invalid_api_key"

        return self.async_show_form(
            step_id="perenual_setup",
            data_schema=vol.Schema({
                vol.Required(CONF_PERENUAL_KEY): str,
            }),
            errors=errors,
        )

    async def async_step_plant_setup(self, user_input=None):
        """Step to search for a plant."""
        errors = {}
        if user_input is not None:
            self._plant_name = user_input["name"]
            search_query = user_input["species_search"]
            self._custom_image = user_input.get("custom_image_url")
            
            if self._selected_source == "local":
                return await self.async_step_plant_setup_local(search_query)

            session = async_get_clientsession(self.hass)
            if self._selected_source == "perenual":
                entries = self._async_current_entries()
                perenual_entry = next((entry for entry in entries if entry.unique_id == "smart_plant_perenual"), None)
                api = PerenualAPI(perenual_entry.data[CONF_PERENUAL_KEY], session)
            else:
                # Use HA language for Wikipedia
                lang = "en"
                if hasattr(self.hass.config, "language") and self.hass.config.language:
                    lang = self.hass.config.language[:2]
                api = WikipediaAPI(session, lang=lang)
            
            self._search_results = await api.search_plants(search_query)
            if not self._search_results:
                errors["base"] = "no_plants_found"
            elif len(self._search_results) == 1:
                return await self.async_step_select_species({"pid": self._search_results[0]["pid"]})
            else:
                return await self.async_step_select_species()

        return self.async_show_form(
            step_id="plant_setup",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("species_search"): str,
                vol.Optional("custom_image_url"): str,
            }),
            errors=errors,
        )

    async def async_step_plant_setup_local(self, query):
        """Search in local plants.json."""
        path = os.path.join(os.path.dirname(__file__), "plants.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                plants = json.load(f)
            
            query = query.lower()
            matches = []
            for pid, info in plants.items():
                if query in pid.lower() or query in info["name"].lower():
                    matches.append({"pid": pid, "alias": info["name"]})
            
            if not matches:
                return await self.async_step_plant_setup({"base": "no_plants_found"})
            
            self._search_results = matches
            if len(matches) == 1:
                return await self.async_step_select_species({"pid": matches[0]["pid"]})
            return await self.async_step_select_species()
        except Exception:
            return await self.async_step_plant_setup({"base": "local_database_error"})

    async def async_step_select_species(self, user_input=None):
        """Step to select a species."""
        if user_input is not None:
            pid = user_input["pid"]
            
            if self._selected_source == "local":
                path = os.path.join(os.path.dirname(__file__), "plants.json")
                with open(path, "r", encoding="utf-8") as f:
                    plants = json.load(f)
                details = plants[pid]
            else:
                session = async_get_clientsession(self.hass)
                if self._selected_source == "perenual":
                    entries = self._async_current_entries()
                    perenual_entry = next((entry for entry in entries if entry.unique_id == "smart_plant_perenual"), None)
                    api = PerenualAPI(perenual_entry.data[CONF_PERENUAL_KEY], session)
                else:
                    api = WikipediaAPI(session)
                details = await api.get_plant_detail(pid)
            
            options = {}
            if self._custom_image:
                options["custom_image_url"] = self._custom_image

            return self.async_create_entry(
                title=f"{self._plant_name} ({details.get('name', pid)})",
                data={
                    "name": self._plant_name,
                    ATTR_PID: pid,
                    ATTR_SPECIES: details.get('name', pid),
                    "details": details
                },
                options=options
            )

        species_options = {p["pid"]: p["alias"] for p in self._search_results}
        return self.async_show_form(
            step_id="select_species",
            data_schema=vol.Schema({
                vol.Required("pid"): vol.In(species_options),
            }),
        )
