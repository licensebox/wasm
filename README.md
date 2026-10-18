# Licensebox for WebAssembly / WASI

A host-assisted wasm32 ABI, validated using Wasmtime and a native Python host on
Linux. The native host owns the Licensebox client, product configuration,
installation credentials, native machine recognition, TLS and signed leases.
The guest receives operation results; it never supplies product keys, raw machine
IDs or a replacement identity. This is not standalone browser licensing.

Install from this repository with `python3 -m pip install .`. The Python client
and Wasmtime versions are pinned in `host-dependencies.txt` (wheel metadata reads this file). Registry publication is
separate. The host must already be configured with administrator-provided public
verification keys. Do not ship administrator tokens or signing secrets.

```python
import wasmtime
from licensebox import Client
from licensebox_wasm import Host
client = Client("myapp", {"myapp-k1": "YOUR_PUBLIC_VERIFICATION_KEY"})
engine = wasmtime.Engine()
store = wasmtime.Store(engine)
linker = wasmtime.Linker(engine)
host = Host(client)  # only require/status operations allowed by default
host.install(linker)
module = wasmtime.Module.from_file(engine, "application.wasm")
instance = linker.instantiate(store, module)
# Invoke your guest's entry point; it calls the documented Licensebox imports.
```

For WASI guests, set an explicitly configured `wasmtime.WasiConfig` on the store
and call `linker.define_wasi()`. Do not inherit host files, environment or native
identity paths just for licensing. The tests instantiate real WASI imports with
no inherited arguments, environment or preopened directories. Hosts should also
configure execution fuel/time limits appropriate for their own guest workload.
Browser, Node and other WASM hosts need their own native integration and tests;
they are not claimed as supported by this release.

## Guest interface

`include/licensebox_wasm.h` declares the three wasm32 imports. Every guest must
export its linear memory as `memory`. The functions are synchronous:

1. `licensebox.request(op_ptr, op_len, args_ptr, args_len)` returns a response handle.
2. `licensebox.read(handle, offset, output_ptr, capacity)` copies a chunk and returns
   its byte count. Zero means end of response. Read the same handle repeatedly.
3. `licensebox.release(handle)` discards the response. Always release, also on errors.

Strings and operation arguments are UTF-8 JSON. Use a positive read capacity; zero is reserved for end of response. Pointer
arguments must be nonnegative signed i32 offsets in the first 2 GiB of memory.
Maximum argument/response size is
1 MiB and maximum outstanding responses is 16. Invalid guest pointers and stale
handles trap, including repeated release. Handle IDs never wrap or reuse within
a host; after the signed-i32 ID range is exhausted, requests trap. Results are JSON: `{"ok":true,"value":...}` or
`{"ok":false,"error":"stable_code"}`. Only a successful `require` response
authorizes protected work. Check before reading or processing user files.
No response contains an installation private key or a signed credential token.

| Operation | Arguments |
| --- | --- |
| `require` | `{"module":"export"}` |
| `status`, `lease`, `modules`, `requests`, `access-link`, `logout` | `{}` |
| `sign_in` | `{"timeout":60}` |
| `request` | `{"modules":["export"],"note":"reason"}` |
| `record` | `{"command":"export","success":true,"elapsed":0.125}` |

The host can explicitly enable additional operations using `allowed_operations`.
Explicit `sign_in` is capped by the host's `sign_in_timeout` (default 60 seconds).
The allowlist governs explicit guest operations. As in the native SDK, a protected
`require`/`lease` can initiate ordinary activation or sign-in after changed terms;
the explicit timeout cap does not alter that native behavior. The default policy
does not guarantee absence of a sign-in UI. Explicit sign-in/seat transfer remains
disallowed by default. Guest
arguments never configure identity, clock, server, storage or verification keys.
Sign-in UI/cancellation belong to the host. Hosts, instances and stores are
thread confined. `host.close()` drops response buffers; the application owns the
native client's lifecycle. Closing is idempotent and permanently disables imports
and invalidates outstanding handles; create a new Host to reopen. Install a
separate Host and linker for each isolated guest instance; do not share a host
between guests. Callback reentry is rejected. No background heartbeat is started.

Unexpired verified cached access can cover eligible transport outages; expired
leases need connectivity. Explicit machine/seat/location refusals persist and
fail closed. Modified host/guest code or cloned native IDs remain software
licensing limitations. A host executing untrusted guests must protect its own
privileged operations independently; guest cooperation is not an isolation boundary.

## Validation

Run `bash ci/test.sh`, then the shared protocol suite with `ci/adapter.sh`.
All client operations cross a real WASM import in the conformance adapter.
Stateless crypto/identity vectors execute in the native host, where these
responsibilities belong. Additional tests cover WASI defaults, host operation
policy, forbidden guest identity overrides, pointer bounds, response ownership
and mutating-call replay avoidance. Additional lifecycle tests cover closed hosts,
stale/exhausted handles, sanitized host faults, finite usage values and callback
reentry. CI also builds a wheel, installs it independently, compiles the packaged
C example against the packaged wasm32 header using clang/lld, and runs it through
real Wasmtime imports. No libc or WASI SDK is needed for that freestanding example.
Fixtures and keys are synthetic.

MIT. Copyright © 2026 [Vijai Kumar](https://meshing.engineer).

## Optional guest heartbeat checkpoints

A trusted application may opt in with
`Host(native_client, allowed_operations={"heartbeat", "status"})`. The guest
operation is `heartbeat` with `{"module":"core"}` and returns
`{"lease":{...},"online":true|false}` inside the ordinary success envelope.
The default allowlist remains `require`/`status`. Heartbeat accepts no product,
keys, server, binding, clock or scheduling override from guest memory.

Heartbeat forces signed renewal through the native Python client with a
three-second network bound. It never starts activation or key rotation and
requires saved verified credentials. Explicit refusals, removed modules, invalid
state and offline expiry fail closed; eligible transport outages may return the
unexpired saved lease with `online=false`, without moving its deadline. Response
handles/chunk reads preserve one execution per request, including heartbeat.

The trusted host owns scheduling and must stop protected work by the last
verified signed expiry independently of a slow check. Read the optional signed
heartbeat interval/grace from the verified lease. This bridge starts no timer or
thread and never stops the application itself. Python/Wasmtime on Linux remains
the validated profile; standalone browser identity remains unsupported.
