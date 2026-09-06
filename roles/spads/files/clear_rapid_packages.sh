#!/bin/bash

set -e -u -o pipefail

if [[ $# -ne 2 ]]; then
    echo "USAGE: ./clear_rapid_packages.sh packages_path unused_days" >&2
    exit 1
fi
packages_path="$1"
unused_days="$2"

mount_options=$(findmnt -T "$packages_path" -n -o OPTIONS)
if [[ ",$mount_options," == *,noatime,* ]]; then
    echo "ERROR: $packages_path is mounted noatime, can't tell which packages are in use" >&2
    exit 1
fi

# pr-downloader refreshes atime on each byar:test refresh check, engine loads
# spds of used packages, but doesn't reopen old ones that were already scaned.
find "$packages_path" -maxdepth 1 -name "*.sdp" -type f -atime "+$unused_days" -delete
