"""Constants for the Vienna Lines integration."""

from datetime import timedelta


DOMAIN = "wienerlinien"
BASE_URL = "http://www.wienerlinien.at/ogd_realtime/monitor"
CONF_STOPS = "stops"
TIME_STR_FORMAT = "%H:%M"
DEFAULT_DEPARTURE_LIMIT = 5
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300  # 5 minutes