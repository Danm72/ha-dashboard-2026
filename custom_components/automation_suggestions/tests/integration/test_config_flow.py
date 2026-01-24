"""Tests for the config flow."""

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.automation_suggestions.const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_CONSISTENCY_THRESHOLD,
    CONF_DOMAIN_FILTER_MODE,
    CONF_FILTERED_DOMAINS,
    CONF_FILTERED_USERS,
    CONF_LOOKBACK_DAYS,
    CONF_MIN_OCCURRENCES,
    CONF_USER_FILTER_MODE,
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

    @pytest.mark.asyncio
    async def test_flow_with_user_filter_exclude_mode(self, hass):
        """Test config flow with user filtering enabled in exclude mode."""
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
                CONF_USER_FILTER_MODE: "exclude",
                CONF_FILTERED_USERS: "uuid1, uuid2",
                CONF_DOMAIN_FILTER_MODE: "none",
                CONF_FILTERED_DOMAINS: "",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_USER_FILTER_MODE] == "exclude"
        assert result["data"][CONF_FILTERED_USERS] == ["uuid1", "uuid2"]

    @pytest.mark.asyncio
    async def test_flow_with_domain_filter_include_mode(self, hass):
        """Test config flow with domain filtering enabled in include mode."""
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
                CONF_USER_FILTER_MODE: "none",
                CONF_FILTERED_USERS: "",
                CONF_DOMAIN_FILTER_MODE: "include",
                CONF_FILTERED_DOMAINS: "nodered,appdaemon",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_DOMAIN_FILTER_MODE] == "include"
        assert result["data"][CONF_FILTERED_DOMAINS] == ["nodered", "appdaemon"]

    @pytest.mark.asyncio
    async def test_flow_with_empty_filter_lists(self, hass):
        """Test that empty filter strings result in empty lists."""
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
                CONF_USER_FILTER_MODE: "none",
                CONF_FILTERED_USERS: "",
                CONF_DOMAIN_FILTER_MODE: "none",
                CONF_FILTERED_DOMAINS: "",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_FILTERED_USERS] == []
        assert result["data"][CONF_FILTERED_DOMAINS] == []


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

    @pytest.mark.asyncio
    async def test_options_flow_with_filters(self, hass, config_entry, mock_analyzer, mock_store):
        """Test options flow can update filter settings."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_ANALYSIS_INTERVAL: 7,
                CONF_LOOKBACK_DAYS: 14,
                CONF_MIN_OCCURRENCES: 5,
                CONF_CONSISTENCY_THRESHOLD: 0.70,
                CONF_USER_FILTER_MODE: "include",
                CONF_FILTERED_USERS: "user-abc-123",
                CONF_DOMAIN_FILTER_MODE: "exclude",
                CONF_FILTERED_DOMAINS: "pyscript, shell_command",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_USER_FILTER_MODE] == "include"
        assert config_entry.options[CONF_FILTERED_USERS] == ["user-abc-123"]
        assert config_entry.options[CONF_DOMAIN_FILTER_MODE] == "exclude"
        assert config_entry.options[CONF_FILTERED_DOMAINS] == ["pyscript", "shell_command"]

    @pytest.mark.asyncio
    async def test_options_flow_domains_normalized_to_lowercase(
        self, hass, config_entry, mock_analyzer, mock_store
    ):
        """Test that domain names are normalized to lowercase."""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_ANALYSIS_INTERVAL: 7,
                CONF_LOOKBACK_DAYS: 14,
                CONF_MIN_OCCURRENCES: 5,
                CONF_CONSISTENCY_THRESHOLD: 0.70,
                CONF_USER_FILTER_MODE: "none",
                CONF_FILTERED_USERS: "",
                CONF_DOMAIN_FILTER_MODE: "include",
                CONF_FILTERED_DOMAINS: "NodeRED, AppDaemon, PyScript",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert config_entry.options[CONF_FILTERED_DOMAINS] == [
            "nodered",
            "appdaemon",
            "pyscript",
        ]
