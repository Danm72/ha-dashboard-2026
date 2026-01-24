"""Root conftest - minimal to allow different test types."""

pytest_plugins = ["pytest_homeassistant_custom_component"]

# Note: e2e tests use their own pytest.ini with -p no:homeassistant to disable
# the plugin and allow real Docker sockets.
