"""Host-assisted Licensebox ABI. Native identity and credentials stay in the host."""
import json
import math
import threading
import wasmtime
from licensebox import LicenseboxError

OPERATIONS=frozenset({"lease","require","status","sign_in","logout","modules","request","requests","access-link","record"})
FIELDS={"lease":set(),"require":{"module"},"status":set(),"sign_in":{"timeout"},"logout":set(),"modules":set(),"request":{"modules","note"},"requests":set(),"access-link":set(),"record":{"command","success","elapsed"}}
LIMIT=1<<20
class Host:
    """Bind one trusted native Client, never guest-supplied product/keys/identity.

    By default guests may only check local status or require a module. Explicitly
    enable other operations for a trusted application. Store/instances are thread
    confined. No filesystem or WASI capabilities are granted by this class.
    """
    def __init__(self,client,*,allowed_operations=frozenset({"require","status"}),sign_in_timeout=60):
        allowed=frozenset(allowed_operations)
        if not allowed<=OPERATIONS or isinstance(sign_in_timeout,bool) or not isinstance(sign_in_timeout,(int,float)) or not math.isfinite(sign_in_timeout) or not 0<sign_in_timeout<=600:raise ValueError("invalid host policy")
        self.client=client;self.allowed=allowed;self.sign_in_timeout=sign_in_timeout
        self._responses={};self._next=1;self._owner=threading.get_ident();self._busy=False;self._closed=False;self._installed=False
    def _thread(self):
        if threading.get_ident()!=self._owner:raise RuntimeError("host is thread confined")
    def _active(self):
        self._thread()
        if self._closed:raise wasmtime.Trap("host is closed")
        if self._busy:raise wasmtime.Trap("host callback reentry")
    @staticmethod
    def _memory(caller):
        memory=caller.get("memory")
        if not isinstance(memory,wasmtime.Memory):raise wasmtime.Trap("guest must export memory")
        return memory
    @staticmethod
    def _bounds(memory,caller,pointer,size):
        if pointer<0 or size<0 or size>LIMIT or pointer+size>memory.data_len(caller):
            raise wasmtime.Trap("invalid guest memory range")
    def _request(self,caller,op_ptr,op_len,args_ptr,args_len):
        self._active()
        if self._next>2147483647:raise wasmtime.Trap("response handles exhausted")
        if len(self._responses)>=16:raise wasmtime.Trap("release outstanding responses")
        memory=self._memory(caller)
        self._bounds(memory,caller,op_ptr,op_len);self._bounds(memory,caller,args_ptr,args_len)
        if op_len>32:raise wasmtime.Trap("invalid operation length")
        self._busy=True
        try:
            try:
                op=bytes(memory.read(caller,op_ptr,op_ptr+op_len)).decode("utf-8")
                args=json.loads(bytes(memory.read(caller,args_ptr,args_ptr+args_len)).decode("utf-8"))
                if op not in self.allowed:raise LicenseboxError("operation_denied")
                if not isinstance(args,dict) or set(args)-FIELDS[op]:raise LicenseboxError("invalid_argument")
                answer={"ok":True,"value":self._call(op,args)}
            except LicenseboxError as e:answer={"ok":False,"error":e.code}
            except (UnicodeError,ValueError,TypeError,KeyError,OverflowError,RecursionError):answer={"ok":False,"error":"invalid_argument"}
            except Exception:
                raise wasmtime.Trap("native host operation failed") from None
            # Unexpected host faults trap; they can never turn into authorization.
            try:
                data=json.dumps(answer,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode()
            except Exception:
                raise wasmtime.Trap("native host result invalid") from None
            if len(data)>LIMIT:data=b'{"ok":false,"error":"response_too_large"}'
            token=self._next;self._next+=1
            self._responses[token]=data
            return token
        finally:self._busy=False
    def _call(self,op,a):
        c=self.client
        if op=="require":
            if not isinstance(a.get("module"),str):raise ValueError("module required")
            return c.require(a["module"])
        if op=="lease":return c.lease()
        if op=="status":return c.status()
        if op=="sign_in":
            timeout=a.get("timeout",self.sign_in_timeout)
            if not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not 0<timeout<=self.sign_in_timeout:raise ValueError("timeout")
            return c.sign_in(timeout=timeout)
        if op=="logout":return c.logout()
        if op=="modules":return c.modules()
        if op=="requests":return c.requests()
        if op=="access-link":return c.access_link()
        if op=="request":
            if not isinstance(a.get("modules"),list) or any(not isinstance(x,str) for x in a["modules"]) or not isinstance(a.get("note",""),str):raise ValueError("request")
            return c.request_access(a["modules"],a.get("note",""))
        if op=="record":
            if not isinstance(a.get("command"),str) or not isinstance(a.get("success"),bool) or not isinstance(a.get("elapsed"),(int,float)) or isinstance(a["elapsed"],bool) or not math.isfinite(a["elapsed"]) or a["elapsed"]<0:raise ValueError("record")
            return c.record(a["command"],a["success"],a["elapsed"])
        raise LicenseboxError("operation_denied")
    def _read(self,caller,token,offset,pointer,capacity):
        self._active()
        if capacity==0:raise wasmtime.Trap("read capacity must be positive")
        data=self._responses.get(token)
        if data is None or offset<0 or offset>len(data):raise wasmtime.Trap("invalid response handle")
        memory=self._memory(caller);self._bounds(memory,caller,pointer,capacity)
        chunk=data[offset:offset+capacity];memory.write(caller,chunk,pointer);return len(chunk)
    def _release(self,token):
        self._active()
        if token not in self._responses:raise wasmtime.Trap("invalid response handle")
        del self._responses[token]
    def install(self,linker):
        """Install imports into an otherwise capability-free Wasmtime Linker."""
        self._active()
        if self._installed:raise RuntimeError("use a separate Host for each guest instance")
        self._installed=True
        i32=wasmtime.ValType.i32()
        try:
            linker.define_func("licensebox","request",wasmtime.FuncType([i32]*4,[i32]),self._request,access_caller=True)
            linker.define_func("licensebox","read",wasmtime.FuncType([i32]*4,[i32]),self._read,access_caller=True)
            linker.define_func("licensebox","release",wasmtime.FuncType([i32],[]),self._release)
        except Exception:
            # A partially installed import table must not remain usable.
            self._closed=True;self._responses.clear()
            raise
    def close(self):
        """Drop response buffers; the application owns the native Client."""
        self._thread()
        if self._busy:raise RuntimeError("host callback reentry")
        self._closed=True;self._responses.clear()
