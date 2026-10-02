"""Constants for the OtO Lawn integration."""

DOMAIN = "oto"

# Polling interval in seconds - OtO device checks in every ~5 minutes,
# so polling faster than that returns stale data.
POLLING_INTERVAL_SEC = 300
