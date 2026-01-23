"""
Test constants shared across test modules.

This module centralizes test configuration values to ensure consistency
across all test environments.
"""

# Long-lived access token for test Home Assistant instance
# This token is embedded in tests/e2e/initial_test_state/.storage/auth
# Expires: 2035 (10+ years from token creation)
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI0Y2MxMWYzOGI3NDMyZGE1OTUyOGUyZDg2NGVhNTgxYyIsImlhdCI6MTc2OTE3ODgxNCwiZXhwIjoyMDUxMjIyNDAwfQ.W0vP43Qs9EKb_kfvsAD6v4H7xYgoHdokFrl8o5HGjfE"

# Test user credentials (for UI access if needed)
TEST_USER = "test"
TEST_PASSWORD = "test"
