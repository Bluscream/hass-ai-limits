"""The AI Limits integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PROVIDER, PLATFORMS
from .coordinator import AILimitsCoordinator

_LOGGER = logging.getLogger(__name__)

type AILimitsConfigEntry = ConfigEntry[AILimitsCoordinator]


def _copy_blueprint(hass: HomeAssistant, src_bp: str, dst_dir: str, dst_bp: str) -> bool:
    """Synchronous blueprint copying function run in the executor."""
    import os
    import shutil
    if os.path.exists(src_bp):
        os.makedirs(dst_dir, exist_ok=True)
        if not os.path.exists(dst_bp) or os.path.getmtime(src_bp) > os.path.getmtime(dst_bp):
            shutil.copy2(src_bp, dst_bp)
            return True
    return False


async def async_setup_entry(
    hass: HomeAssistant, entry: AILimitsConfigEntry
) -> bool:
    """Set up AI Limits from a config entry."""
    _LOGGER.info(
        "Setting up AI Limits account '%s' (provider=%s)",
        entry.title,
        entry.data.get(CONF_PROVIDER),
    )
    coordinator = AILimitsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register static path for the Lovelace card
    try:
        from homeassistant.components.http import StaticPathConfig
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path="/ai-limits-card/ai-limits-card.js",
                path=hass.config.path("custom_components/ai_limits/frontend/ai-limits-card.js"),
                cache_headers=False,
            )
        ])
    except (ImportError, AttributeError):
        # Fallback for older Home Assistant versions
        try:
            hass.http.register_static_path(
                "/ai-limits-card/ai-limits-card.js",
                hass.config.path("custom_components/ai_limits/frontend/ai-limits-card.js"),
                cache_headers=False,
            )
        except RuntimeError:
            pass # Already registered by another config entry
    except RuntimeError:
        pass # Already registered by another config entry

    # Auto-register Lovelace card resource
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace and hasattr(lovelace, "resources"):
            resources = lovelace.resources
            exists = False
            for item in resources.async_items():
                if item.get("url") == "/ai-limits-card/ai-limits-card.js":
                    exists = True
                    break
            if not exists:
                await resources.async_create_item({
                    "res_type": "module",
                    "url": "/ai-limits-card/ai-limits-card.js"
                })
    except Exception as err:
        _LOGGER.warning("Could not auto-register Lovelace resource: %s", err)

    # Auto-copy blueprint to config blueprints directory (non-blocking executor)
    try:
        import os
        src_bp = hass.config.path("custom_components", "ai_limits", "blueprints", "ai_limits_reset_notification.yaml")
        dst_dir = hass.config.path("blueprints", "automation", "ai_limits")
        dst_bp = os.path.join(dst_dir, "ai_limits_reset_notification.yaml")
        copied = await hass.async_add_executor_job(_copy_blueprint, hass, src_bp, dst_dir, dst_bp)
        if copied:
            _LOGGER.info("Copied AI Limits reset notification blueprint to %s", dst_bp)
    except Exception as err:
        _LOGGER.warning("Could not auto-copy blueprint: %s", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AILimitsConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading AI Limits account '%s'", entry.title)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: AILimitsConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
