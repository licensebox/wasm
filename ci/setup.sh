#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y clang lld
python3 -m pip install "setuptools>=68" wheel
python3 -m pip install .
