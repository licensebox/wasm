/* Actual wasm32 guest using the shipped ABI, with no WASI filesystem imports.
 * The embedding application parses response JSON and checks ok before work.
 * Never repeat a request just to size its response. */
#include "licensebox_wasm.h"
static char response[32768];
__attribute__((export_name("response_pointer")))
int32_t response_pointer(void) { return (int32_t)(uintptr_t)response; }
static int32_t invoke(const char *operation,int32_t operation_length,const char *arguments,int32_t arguments_length) {
 int32_t handle=licensebox_request(operation,operation_length,arguments,arguments_length),offset=0;
 for (;;) {
  int32_t remaining=(int32_t)sizeof(response)-offset;
  if(remaining==0){licensebox_release(handle);return -1;}
  int32_t count=licensebox_read(handle,offset,response+offset,remaining);
  if(count<0||count>remaining){licensebox_release(handle);return -1;}
  if(!count)break;
  offset+=count;
 }
 licensebox_release(handle);
 return offset;
}

__attribute__((export_name("require_core")))
int32_t require_core(void) { return invoke("require",7,"{\"module\":\"core\"}",17); }
__attribute__((export_name("local_status")))
int32_t local_status(void) { return invoke("status",6,"{}",2); }

/* Opt-in host capability. The embedding app checks ok and the signed deadline. */
__attribute__((export_name("heartbeat_core")))
int32_t heartbeat_core(void) { return invoke("heartbeat",9,"{\"module\":\"core\"}",17); }
