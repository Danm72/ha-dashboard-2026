"""
E2E test fixtures using testcontainers.

Spins up a real Home Assistant Docker container with our custom component
installed to test against actual HA APIs.

Requires: pip install testcontainers requests docker
"""

import logging
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path

import pytest
import pytest_socket
import requests
from testcontainers.core.container import DockerContainer

# Enable socket access IMMEDIATELY at import time for Docker communication
# This must happen before any fixtures are collected
pytest_socket.enable_socket()

logger = logging.getLogger(__name__)


def pytest_configure(config):
    """Configure pytest to allow socket for e2e tests."""
    config.addinivalue_line(
        "markers", "enable_socket: mark test to enable socket access"
    )


# Test token - must match what's in initial_test_state/.storage/auth
# For initial setup, you'll need to create this manually once
TEST_TOKEN = os.environ.get("HA_TEST_TOKEN", "")


def _setup_config_permissions(config_path: Path) -> None:
    """Set up proper permissions for Home Assistant config directory."""
    for root, dirs, files in os.walk(config_path):
        for d in dirs:
            os.chmod(
                os.path.join(root, d),
                stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH,
            )
        for f in files:
            os.chmod(
                os.path.join(root, f),
                stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH,
            )


@pytest.fixture(scope="session")
def ha_container():
    """Create Home Assistant container with our custom component installed."""
    logger.info("Creating Home Assistant container...")

    # Create temporary directory for this test session
    temp_dir = tempfile.mkdtemp(prefix="ha_e2e_test_")
    config_path = Path(temp_dir)

    # Copy initial test state
    initial_state_path = Path(__file__).parent / "initial_test_state"
    if initial_state_path.exists():
        shutil.copytree(initial_state_path, config_path, dirs_exist_ok=True)
        logger.info(f"Copied initial state from {initial_state_path}")
    else:
        # Create minimal config
        (config_path / "configuration.yaml").write_text(
            "default_config:\n\nrecorder:\n  purge_keep_days: 5\n"
        )
        logger.info("Created minimal config")

    # Copy our custom component into the container's config
    custom_components_src = Path(__file__).parent.parent.parent / "custom_components"
    custom_components_dst = config_path / "custom_components"
    if custom_components_src.exists():
        shutil.copytree(custom_components_src, custom_components_dst, dirs_exist_ok=True)
        logger.info(f"Installed custom_components from {custom_components_src}")

    # Set permissions
    _setup_config_permissions(config_path)

    # Create container
    container = (
        DockerContainer("ghcr.io/home-assistant/home-assistant:stable")
        .with_exposed_ports(8123)
        .with_volume_mapping(str(config_path), "/config", "rw")
        .with_env("TZ", "UTC")
    )

    with container:
        host_port = container.get_exposed_port(8123)
        base_url = f"http://localhost:{host_port}"

        logger.info(f"Home Assistant starting on {base_url}")

        # Wait for API to be ready
        _wait_for_ha_ready(base_url, timeout=120)

        logger.info("Home Assistant ready")

        container_info = {
            "container": container,
            "port": host_port,
            "base_url": base_url,
            "config_path": str(config_path),
        }

        try:
            yield container_info
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Cleanup completed")


def _wait_for_ha_ready(base_url: str, timeout: int = 120) -> None:
    """Wait for Home Assistant API to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Check API without auth first (should return 401 if HA is ready)
            resp = requests.get(f"{base_url}/api/", timeout=5)
            if resp.status_code in (200, 401):
                # Give HA a bit more time to fully stabilize
                time.sleep(5)
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    raise TimeoutError(f"Home Assistant did not start within {timeout}s")


@pytest.fixture(scope="session")
def ha_url(ha_container):
    """Return the Home Assistant URL."""
    return ha_container["base_url"]


@pytest.fixture(scope="session")
def ha_token():
    """Return the test token for authenticated API calls."""
    if not TEST_TOKEN:
        pytest.skip("HA_TEST_TOKEN not set - run initial setup first")
    return TEST_TOKEN


@pytest.fixture
def ha_api(ha_url, ha_token):
    """Return a configured requests session for HA API calls."""
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {ha_token}"
    session.headers["Content-Type"] = "application/json"

    def api_call(method: str, endpoint: str, **kwargs):
        url = f"{ha_url}{endpoint}"
        return session.request(method, url, timeout=30, **kwargs)

    return api_call
