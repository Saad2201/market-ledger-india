#!/usr/bin/env bash
# Nightly BSE fetch -> docs/data.json. Resumable: only new days are downloaded.
# Cron (server in any timezone), twice because BSE sometimes publishes late:
#   CRON_TZ=Asia/Kolkata
#   30 19,22 * * * /path/to/nightly.sh >> /path/to/nightly.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"
python3 bse_fetch.py --datasets cm_bhav fo_summary delivery --site-dir docs
