"""Constants for the Vienna Lines integration."""

from datetime import timedelta


DOMAIN = "wienerlinien"
CONF_STOPS = "stops"
TIME_STR_FORMAT = "%H:%M"
DEFAULT_DEPARTURE_LIMIT = 5
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300  # 5 minutes
DEFAULT_TRAFFIC_SCAN_INTERVAL = 300  # 5 minutes for traffic info updates
ENTITY_PREFIX = "wl_"  # Prefix for all entities

BASE_URL = "http://www.wienerlinien.at/ogd_realtime/monitor"
BASE_TIL = "http://www.wienerlinien.at/ogd_realtime/trafficInfoList?name=stoerunglang&name=stoerungkurz&relatedLine={}"