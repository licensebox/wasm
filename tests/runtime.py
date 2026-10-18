import json
from pathlib import Path
import wasmtime
from licensebox_wasm import Host
class Guest:
    def __init__(self,client,**options):
        self.engine=wasmtime.Engine();self.store=wasmtime.Store(self.engine)
        self.store.set_wasi(wasmtime.WasiConfig())
        self.host=Host(client,**options);linker=wasmtime.Linker(self.engine);linker.define_wasi();self.host.install(linker)
        self.instance=linker.instantiate(self.store,wasmtime.Module.from_file(self.engine,str(Path(__file__).with_name("bridge.wat"))))
        self.exports=self.instance.exports(self.store);self.memory=self.exports["memory"]
    def call(self,op,args=None):
        operation=op.encode();arguments=json.dumps(args or {},ensure_ascii=False).encode()
        self.memory.write(self.store,operation,0);self.memory.write(self.store,arguments,128)
        token=self.exports["request"](self.store,0,len(operation),128,len(arguments))
        data=bytearray();offset=0
        try:
            while True:
                count=self.exports["read"](self.store,token,offset,1048704,4096)
                if not count:break
                data.extend(self.memory.read(self.store,1048704,1048704+count));offset+=count
            return json.loads(data)
        finally:self.exports["release"](self.store,token)
