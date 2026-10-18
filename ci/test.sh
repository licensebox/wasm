#!/usr/bin/env bash
set -euo pipefail
python3 -m unittest discover -s tests -p "test_*.py"
mkdir -p build/wheels build/consumer-site
python3 -m pip wheel --no-deps --no-build-isolation . -w build/wheels
python3 -m pip install --no-deps --target build/consumer-site --upgrade build/wheels/*.whl
compiler=${CLANG:-clang}
linker=${WASM_LD:-wasm-ld}
if ! command -v "$linker" >/dev/null && command -v wasm-ld-18 >/dev/null; then linker=wasm-ld-18; fi
"$compiler" --target=wasm32-unknown-unknown -ffreestanding -nostdlib -O2 \
  -Ibuild/consumer-site/include/licensebox -Wl,--no-entry -Wl,--export-memory -Wl,--initial-memory=131072 \
  "-fuse-ld=$(command -v "$linker")" build/consumer-site/share/licensebox-wasm/examples/guest.c -o build/guest.wasm
root=$PWD
# Avoid importing the checkout when validating the installed package.
(cd build && PYTHONPATH="$root/build/consumer-site:${PYTHONPATH:-}" python3 "$root/tests/consumer.py" "$root/build/guest.wasm" "$root/build/consumer-site")
