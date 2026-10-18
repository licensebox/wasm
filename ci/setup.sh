#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y clang lld
python3 -m pip install "setuptools>=68" wheel
python3 -m pip install .
# A feature CI run can substitute only the fixed public full-SHA Python pin.
candidate=$(python3 -B ci/candidate-host.py)
if test -n "$candidate"; then
  python3 -m pip install --force-reinstall "$candidate"
fi
