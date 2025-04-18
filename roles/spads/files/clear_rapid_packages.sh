#!/bin/bash

set -e -u -o pipefail

if [[ $# -ne 2 ]]; then
    echo "USAGE: ./clear_rapid_packages.sh packages_path older_then_days"
    exit 1
fi
packages_path="$1"
older_then_days="$2"

newest_file=$(find "$packages_path" -maxdepth 1 -name "*.sdp" -type f -printf '%T@ %p\0' \
    | sort -z -nr | head -z -n 1 | cut -z -d' ' -f2-)
find "$packages_path" -maxdepth 1 -name "*.sdp" -type f -mtime "+$older_then_days" -not -path "$newest_file" -delete
