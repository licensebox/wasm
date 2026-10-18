"""Run outside the source tree with only the installed wheel import path."""
import json
from pathlib import Path
import sys
import tempfile
from licensebox import Client
import wasmtime
import licensebox_wasm
from licensebox_wasm import Host
assert str(Path(licensebox_wasm.__file__).resolve()).startswith(str(Path(sys.argv[2]).resolve()))
class NativeClient:
    heartbeat_calls=0
    def heartbeat(self,name):
        self.heartbeat_calls+=1
        return {'lease':{'modules':[name]},'online':False}
    def require(self,name):
        assert name=='core'
        return {'modules':['core'],'synthetic':'x'*10000}
engine=wasmtime.Engine();store=wasmtime.Store(engine);linker=wasmtime.Linker(engine)
client=NativeClient();host=Host(client,allowed_operations={'require','status','heartbeat'});host.install(linker)
instance=linker.instantiate(store,wasmtime.Module.from_file(engine,sys.argv[1]))
exports=instance.exports(store)
count=exports['require_core'](store)
assert count>10000
pointer=exports['response_pointer'](store)
answer=json.loads(bytes(exports['memory'].read(store,pointer,pointer+count)))
assert answer['ok'] and answer['value']['modules']==['core']
assert host._responses=={}
count=exports['heartbeat_core'](store);pointer=exports['response_pointer'](store)
answer=json.loads(bytes(exports['memory'].read(store,pointer,pointer+count)))
assert answer=={'ok':True,'value':{'lease':{'modules':['core']},'online':False}}
assert client.heartbeat_calls==1 and host._responses=={}
host.close()
# The independently installed host also wraps the real public native client;
# status with empty synthetic storage is local and never contacts a server.
with tempfile.TemporaryDirectory(prefix='licensebox-wasm-consumer-') as directory:
    client=Client('demo',{'synthetic':'A6EHv_POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg'},directory=directory)
    native_host=Host(client,allowed_operations={'status','heartbeat'});native_linker=wasmtime.Linker(engine);native_host.install(native_linker)
    native_instance=native_linker.instantiate(store,wasmtime.Module.from_file(engine,sys.argv[1]))
    native_exports=native_instance.exports(store)
    count=native_exports['local_status'](store);pointer=native_exports['response_pointer'](store)
    result=json.loads(bytes(native_exports['memory'].read(store,pointer,pointer+count)))
    assert result=={'ok':False,'error':'not_signed_in'}
    count=native_exports['heartbeat_core'](store);pointer=native_exports['response_pointer'](store)
    result=json.loads(bytes(native_exports['memory'].read(store,pointer,pointer+count)))
    assert result=={'ok':False,'error':'not_signed_in'}
    assert not Path(directory,'install.key').exists()
    native_host.close()
print('PASS: installed wheel, compiled C wasm32 header ABI, chunk reads and handle release')
