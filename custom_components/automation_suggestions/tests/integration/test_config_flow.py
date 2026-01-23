"""Tests for the config flow."""

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.automation_suggestions.const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    DOMAIN,
)


class TestConfigFlow:
    """Test the config flow."""

    @pytest.mark.asyncio
    async def test_flow_init(self, hass):
        """Test flow initialization shows user form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_flow_user_step_success(self, hass):
        """Test successful config flow completion."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ANALYSIS_INTERVAL: 7,
                CONF_LOOKBACK_DAYS: 14,
                CONF_MIN_OCCURRENCES: 5,
                CONF_CONSISTENCY_THRESHOLD: 0.70,
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Automation Suggestions"
        assert result["data"][CONF_ANALYSIS_INTERVAL] == 7
        assert result["data"][CONF_LOOKBACK_DAYS] == 14

    @pytest.mark.asyncio
    async def test_flow_already_configured(self, hass, config_entry):
        """Test we abort if already configured."""
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


class TestOptionsFlow:
    """Test the options flow."""

    @pytest.mark.asyncio
    async def test_options_flow_init(self, hass, config_entry, mock_analyzer, mock_store):
        """Test options flow shows init form."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_flow_update(self, hass, config_entry, mock_analyzer, mock_store):
        """Test options flow allows reconfiguration."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_ANALYSIS_INTERVAL: 14,
                CONF_LOOKBACK_DAYS: 21,
                CONF_MIN_OCCURRENCES: 3,
                CONF_CONSISTENCY_THRESHOLD: 0.80,
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_ANALYSIS_INTERVAL] == 14
