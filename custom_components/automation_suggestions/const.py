"""Constants for the Automation Suggestions integration."""

DOMAIN = "automation_suggestions"

# Config keys
CONF_ANALYSIS_INTERVAL = "analysis_interval"
CONF_LOOKBACK_DAYS = "lookback_days"
CONF_MIN_OCCURRENCES = "min_occurrences"
CONF_CONSISTENCY_THRESHOLD = "consistency_threshold"
CONF_USER_FILTER_MODE = "user_filter_mode"
CONF_FILTERED_USERS = "filtered_users"
CONF_DOMAIN_FILTER_MODE = "domain_filter_mode"
CONF_FILTERED_DOMAINS = "filtered_domains"

# Defaults
DEFAULT_ANALYSIS_INTERVAL = 7  # days
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_MIN_OCCURRENCES = 2
DEFAULT_CONSISTENCY_THRESHOLD = 0.70
DEFAULT_TIME_WINDOW_MINUTES = 30
DEFAULT_USER_FILTER_MODE = "none"
DEFAULT_FILTERED_USERS: list[str] = []
DEFAULT_DOMAIN_FILTER_MODE = "none"
DEFAULT_FILTERED_DOMAINS: list[str] = []

# Notification threshold for high-confidence suggestions
HIGH_CONFIDENCE_THRESHOLD = 0.80

# Domains to track
TRACKED_DOMAINS = [
    "light",
    "switch",
    "cover",
    "climate",
    "scene",
    "script",
    "input_number",
    "input_boolean",
    "input_select",
    "input_datetime",
    "input_button",
]

# Domain to emoji mapping for notifications and card UI
DOMAIN_EMOJI_MAP: dict[str, str] = {
    "light": "💡",
    "switch": "🔌",
    "cover": "🚪",
    "climate": "🌡️",
    "scene": "🎬",
    "script": "📜",
    "input_number": "⚙️",
    "input_boolean": "⚙️",
    "input_select": "⚙️",
    "input_datetime": "⚙️",
    "input_button": "⚙️",
}

DEFAULT_EMOJI = "📋"
