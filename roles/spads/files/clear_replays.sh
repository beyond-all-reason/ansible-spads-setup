#!/bin/bash

set -e -u -o pipefail

if [[ $# -ne 2 ]]; then
    echo "USAGE: ./clear_replays.sh spads_cluster_files min_free_space_kb"
    exit 1
fi
spads_cluster_files="$1"
min_free_space_kb="$2"

for days in $(seq 7 -1 1); do
    echo "clearing replays older then $days days"
    find "$spads_cluster_files" -name "*.sdfz" -mtime "+$days" -delete
    if (( $(df --output=avail -k "$spads_cluster_files" | tail -n1) > "$min_free_space_kb" )); then
        break
    else
        echo "still less then ${min_free_space_kb}KiB available space..."
    fi
done
