"""
E2E test fixtures using testcontainers or live Home Assistant.

Supports two modes:
- Docker mode (default): Spins up a real Home Assistant Docker container with
  our custom component installed to test against actual HA APIs.
- Live mode (--live flag): Connects to a running Home Assistant instance using
  environment variables for URL and token.

Docker mode requires: pip install testcontainers requests docker
Live mode requires: HA_LIVE_URL and HA_LIVE_TOKEN environment variables
"""

import logging
import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests

# Add tests directory to path for test_constants import
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_constants import TEST_TOKEN  # noqa: E402

logger = logging.getLogger(__name__)


# Load environment variables from .env.e2e if it exists
def _load_env_file():
    """Load environment variables from .env.e2e file if it exists."""
    env_file = Path(__file__).parent.parent.parent / ".env.e2e"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            logger.info(f"Loaded environment from {env_file}")
        except ImportError:
            # Fallback: parse the file manually
            logger.info(f"python-dotenv not installed, parsing {env_file} manually")
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()
                        # Remove surrounding quotes if present
                        if value and value[0] == value[-1] and value[0] in ('"', "'"):
                            value = value[1:-1]
                        os.environ.setdefault(key, value)


_load_env_file()


# Auto-detect Docker socket location for Docker Desktop on macOS
def _configure_docker_socket():
    """Configure Docker socket for Docker Desktop on macOS."""
    import platform

    if os.environ.get("DOCKER_HOST"):
        return  # Already configured

    if platform.system() == "Darwin":
        # Docker Desktop on Mac uses this socket location
        mac_socket = os.path.expanduser("~/.docker/run/docker.sock")
        if os.path.exists(mac_socket):
            os.environ["DOCKER_HOST"] = f"unix://{mac_socket}"
            logger.info(f"Auto-configured DOCKER_HOST={os.environ['DOCKER_HOST']}")


_configure_docker_socket()


def pytest_addoption(parser):
    """Add command line options for e2e tests."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run e2e tests against a live Home Assistant instance instead of Docker",
    )


def pytest_configure(config):
    """Configure pytest markers for e2e tests.

    Note: pytest-homeassistant-custom-component is disabled via pytest.ini
    to allow Docker/testcontainers to work properly.
    """
    config.addinivalue_line(
        "markers", "synthetic_data: mark test as requiring synthetic test data (Docker mode only)"
    )
    config.addinivalue_line(
        "markers", "live_only: mark test as requiring a live Home Assistant instance"
    )


def pytest_collection_modifyitems(config, items):
    """Skip tests based on mode (live vs Docker)."""
    is_live = config.getoption("--live")

    skip_synthetic = pytest.mark.skip(
        reason="Test requires synthetic data from Docker container (not available in --live mode)"
    )
    skip_live_only = pytest.mark.skip(
        reason="Test requires --live mode with a real Home Assistant instance"
    )

    for item in items:
        # Skip synthetic_data tests in live mode
        if is_live and "synthetic_data" in item.keywords:
            item.add_marker(skip_synthetic)
        # Skip live_only tests when NOT in live mode
        if not is_live and "live_only" in item.keywords:
            item.add_marker(skip_live_only)


# Live mode configuration
LIVE_URL_DEFAULT = "http://homeassistant.local:8123"


def _get_live_url():
    """Get live Home Assistant URL from environment."""
    url = os.environ.get("HA_LIVE_URL", LIVE_URL_DEFAULT)
    # Normalize: remove trailing slash
    return url.rstrip("/")


def _get_live_token():
    """Get live Home Assistant token from environment."""
    token = os.environ.get("HA_LIVE_TOKEN")
    if not token:
        raise ValueError(
            "HA_LIVE_TOKEN environment variable is required for --live mode. "
            "Create a long-lived access token in Home Assistant and set it in .env.e2e"
        )
    return token


def _validate_live_connection(url: str, token: str) -> None:
    """Validate that we can connect to the live Home Assistant instance."""
    try:
        resp = requests.get(
            f"{url}/api/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 401:
            raise ValueError(
                f"Authentication failed for {url}. Check your HA_LIVE_TOKEN."
            )
        if resp.status_code != 200:
            raise ValueError(
                f"Unexpected response from {url}: {resp.status_code} {resp.text}"
            )
        logger.info(f"Successfully connected to live Home Assistant at {url}")
    except requests.exceptions.ConnectionError as e:
        raise ValueError(
            f"Cannot connect to Home Assistant at {url}. "
            f"Ensure Home Assistant is running and accessible. Error: {e}"
        ) from e


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
def is_live_mode(request):
    """Return True if running in live mode, False for Docker mode."""
    return request.config.getoption("--live")


@pytest.fixture(scope="session")
def ha_container(request):
    """Create Home Assistant container with our custom component installed.

    In live mode, this fixture is a no-op and returns None.
    """
    if request.config.getoption("--live"):
        # Live mode: no container needed
        logger.info("Running in LIVE mode - skipping Docker container")
        yield None
        return

    logger.info("Running in DOCKER mode - starting container")

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

    # Import here to avoid loading testcontainers in live mode
    from testcontainers.core.container import DockerContainer

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
def ha_url(request, ha_container):
    """Return the Home Assistant URL.

    In live mode, returns HA_LIVE_URL from environment.
    In Docker mode, returns the container's URL.
    """
    if request.config.getoption("--live"):
        return _get_live_url()
    return ha_container["base_url"]


@pytest.fixture(scope="session")
def ha_token(request):
    """Return the token for authenticated API calls.

    In live mode, returns HA_LIVE_TOKEN from environment.
    In Docker mode, returns the test token.
    """
    if request.config.getoption("--live"):
        token = _get_live_token()
        # Validate connection before returning
        url = _get_live_url()
        _validate_live_connection(url, token)
        return token
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
