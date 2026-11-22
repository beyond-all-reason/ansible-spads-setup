#!/bin/bash
# Reboots the host when a reboot is required after package upgrades or when
# the host has been up for too long. Given services are stopped first, all
# in parallel, so e.g. SPADS can wait for the ongoing games to finish.
#
# Usage: maintenance_reboot.sh <max uptime in days> [service to stop]...
set -euo pipefail

notify() {
	[[ -n "${DISCORD_WEBHOOK_URL:-}" ]] || return 0
	curl -sSf -o /dev/null \
		--connect-timeout 5 --max-time 10 \
		--retry 3 --retry-connrefused --retry-max-time 45 \
		-H "Content-Type: application/json" \
		-d "$(jo -- -s username="${DISCORD_USERNAME:-$(hostname)}" -s content="$1")" \
		"$DISCORD_WEBHOOK_URL" || echo "Warning: Discord notification failed" >&2
}

max_uptime_days="$1"
shift
uptime_seconds=$(cut -d. -f1 /proc/uptime)

if [[ -f /run/reboot-required ]]; then
	reason="Reboot required by packages: $(paste -sd ' ' /run/reboot-required.pkgs 2>/dev/null || true)"
elif (( uptime_seconds > max_uptime_days * 86400 )); then
	reason="Uptime of $((uptime_seconds / 86400)) days is over $max_uptime_days days"
else
	echo "Reboot not needed"
	exit 0
fi

echo "$reason"
if (( $# > 0 )); then
	echo "Stopping $*"
	notify "$reason. Stopping $*."
	systemctl stop "$@"
else
	notify "$reason"
fi
echo "Rebooting"
notify "Rebooting"
systemctl reboot
