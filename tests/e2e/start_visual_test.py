#!/usr/bin/env python3
"""Start Home Assistant container for visual testing.

This script starts a Home Assistant Docker container with the custom component
installed and keeps it running for manual visual testing via browser.

Usage:
    python tests/e2e/start_visual_test.py

The script will print the URL to access Home Assistant and wait for you to
press Enter to shut down the container.
"""

import logging
import os
import platform
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def configure_docker_socket():
    """Configure Docker socket for Docker Desktop on macOS."""
    if os.environ.get("DOCKER_HOST"):
        return

    if platform.system() == "Darwin":
        mac_socket = os.path.expanduser("~/.docker/run/docker.sock")
        if os.path.exists(mac_socket):
            os.environ["DOCKER_HOST"] = f"unix://{mac_socket}"
            logger.info(f"Auto-configured DOCKER_HOST={os.environ['DOCKER_HOST']}")


def setup_config_permissions(config_path: Path) -> None:
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


def wait_for_ha_ready(base_url: str, timeout: int = 120) -> None:
    """Wait for Home Assistant API to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{base_url}/api/", timeout=5)
            if resp.status_code in (200, 401):
                time.sleep(5)
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    raise TimeoutError(f"Home Assistant did not start within {timeout}s")


def main():
    configure_docker_socket()

    # Import testcontainers
    try:
        from testcontainers.core.container import DockerContainer
    except ImportError:
        logger.error("testcontainers not installed. Run: pip install testcontainers")
        sys.exit(1)

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="ha_visual_test_")
    config_path = Path(temp_dir)

    logger.info(f"Created temp config directory: {config_path}")

    # Copy initial test state if exists
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

    # Copy our custom component
    custom_components_src = Path(__file__).parent.parent.parent / "custom_components"
    custom_components_dst = config_path / "custom_components"
    if custom_components_src.exists():
        shutil.copytree(custom_components_src, custom_components_dst, dirs_exist_ok=True)
        logger.info(f"Installed custom_components from {custom_components_src}")
    else:
        logger.error(f"Custom components not found at {custom_components_src}")
        sys.exit(1)

    # Set permissions
    setup_config_permissions(config_path)

    # Create container
    container = (
        DockerContainer("ghcr.io/home-assistant/home-assistant:stable")
        .with_exposed_ports(8123)
        .with_volume_mapping(str(config_path), "/config", "rw")
        .with_env("TZ", "UTC")
    )

    logger.info("Starting Home Assistant container...")

    try:
        container.start()
        host_port = container.get_exposed_port(8123)
        base_url = f"http://localhost:{host_port}"

        logger.info(f"Home Assistant starting on {base_url}")
        logger.info("Waiting for Home Assistant to be ready...")

        wait_for_ha_ready(base_url, timeout=120)

        print("\n" + "=" * 60)
        print("HOME ASSISTANT READY FOR VISUAL TESTING")
        print("=" * 60)
        print(f"\nURL: {base_url}")
        print("\nTo test the Lovelace card:")
        print("1. Complete onboarding (if fresh container)")
        print("2. Go to Settings > Dashboards > Resources")
        print("3. Add resource: /automation_suggestions/automation-suggestions-card.js")
        print("4. Create a new dashboard card using type: custom:automation-suggestions-card")
        print("\n" + "=" * 60)
        print("Press Enter to shut down the container...")
        print("=" * 60 + "\n")

        input()

    finally:
        logger.info("Stopping container...")
        container.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info("Cleanup completed")


if __name__ == "__main__":
    main()
