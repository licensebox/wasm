#ifndef LICENSEBOX_WASM_H
#define LICENSEBOX_WASM_H
#include <stdint.h>
/* Wasm32 ABI. Guest memory must be exported as "memory". JSON UTF-8 arguments.
 * request returns a host-owned response handle. read copies up to capacity bytes
 * at offset, returning bytes copied (zero at EOF). Capacity must be positive.
 * Always release the handle once. Stale handles trap; close invalidates all.
 * At most 16 outstanding responses, maximum 1 MiB each. Invalid pointers trap.
 * Guest pointer arguments must be nonnegative signed i32 (first 2 GiB).
 * Responses are {"ok":true,"value":...} or {"ok":false,"error":"stable_code"}.
 * A failed call never authorizes protected work. Never repeat a mutating request
 * merely to size a buffer: read the same response handle in chunks instead. */
#if !defined(__wasm32__)
#error "This header targets a wasm32 guest; use the native SDK in the host."
#endif
__attribute__((import_module("licensebox"),import_name("request")))
int32_t licensebox_request(const char *operation,int32_t operation_length,const char *arguments,int32_t arguments_length);
__attribute__((import_module("licensebox"),import_name("read")))
int32_t licensebox_read(int32_t response,int32_t offset,char *output,int32_t capacity);
__attribute__((import_module("licensebox"),import_name("release")))
void licensebox_release(int32_t response);
#endif
