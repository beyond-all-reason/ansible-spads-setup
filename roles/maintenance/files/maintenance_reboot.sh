#!/bin/bash
# Reboots the host when a reboot is required after package upgrades or when
# the host has been up for too long. Given services are stopped first, all
# in parallel, so e.g. SPADS can wait for the ongoing games to finish.
#
# Usage: maintenance_reboot.sh <max uptime in days> [service to stop]...
set -euo pipefail

max_uptime_days="$1"
shift
uptime_seconds=$(cut -d. -f1 /proc/uptime)

if [[ -f /run/reboot-required ]]; then
	echo "Reboot required by packages: $(tr '\n' ' ' < /run/reboot-required.pkgs 2>/dev/null || true)"
elif (( uptime_seconds > max_uptime_days * 86400 )); then
	echo "Uptime of $((uptime_seconds / 86400)) days is over $max_uptime_days days"
else
	echo "Reboot not needed"
	exit 0
fi

if (( $# > 0 )); then
	echo "Stopping $*"
	systemctl stop "$@"
fi
echo "Rebooting"
systemctl reboot
