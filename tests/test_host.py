import unittest
import gc
import weakref
import json
import math
import threading
import wasmtime
from runtime import Guest
from licensebox_wasm import Host, OPERATIONS, LIMIT
class NativeClient:
    def __init__(self):self.calls=0
    def require(self,module):self.calls+=1;return {'modules':[module],'owned':'x'*10000}
    def status(self):return {'modules':['core']}
class HostTest(unittest.TestCase):
    def test_wasi_guest_has_no_inherited_capabilities(self):
        g=Guest(NativeClient())
        self.assertEqual(g.exports["wasi_argc"](g.store),0)
        self.assertEqual(g.exports["wasi_envc"](g.store),0)
        self.assertEqual(g.exports["wasi_preopen"](g.store),8)  # WASI EBADF: no preopens
    def test_operation_policy_and_identity_configuration(self):
        c=NativeClient();g=Guest(c)
        self.assertEqual(g.call('sign_in',{'timeout':1}),{'ok':False,'error':'operation_denied'})
        for field in ['binding','machine_binding','clock','product','keys','server','directory','version','ca_bundle']:
            self.assertEqual(g.call('require',{'module':'core',field:'fake'}),{'ok':False,'error':'invalid_argument'})
        self.assertEqual(c.calls,0)
        self.assertTrue(g.call('require',{'module':'core'})['ok'])
        self.assertEqual(c.calls,1)
    def test_paged_response_does_not_repeat_operation(self):
        c=NativeClient();g=Guest(c)
        self.assertEqual(len(g.call('require',{'module':'core'})['value']['owned']),10000)
        self.assertEqual(c.calls,1)
        self.assertEqual(g.host._responses,{})
    def test_heartbeat_is_explicit_host_capability_and_executes_once(self):
        class Client(NativeClient):
            def heartbeat(self,module):
                self.calls+=1
                return {'lease':{'modules':[module],'expires':'2030-01-01T00:00:00Z'},'online':False}
        c=Client();default=Guest(c)
        self.assertEqual(default.call('heartbeat',{'module':'core'}),{'ok':False,'error':'operation_denied'})
        guest=Guest(c,allowed_operations={'heartbeat'})
        for args in [{},{'module':''},{'module':True},{'module':'core\0other'},{'module':'core','binding':'forbidden'},{'module':'core','clock':0}]:
            self.assertEqual(guest.call('heartbeat',args),{'ok':False,'error':'invalid_argument'})
        self.assertEqual(c.calls,0)
        self.assertEqual(guest.call('heartbeat',{'module':'core'}),{'ok':True,'value':{'lease':{'modules':['core'],'expires':'2030-01-01T00:00:00Z'},'online':False}})
        self.assertEqual(c.calls,1)
        self.assertEqual(guest.host._responses,{})
    def test_invalid_memory_and_handles_trap(self):
        g=Guest(NativeClient())
        with self.assertRaises(wasmtime.Trap):g.exports['request'](g.store,-1,4,0,2)
        with self.assertRaises(wasmtime.Trap):g.exports['read'](g.store,123,0,0,4)
        self.assertEqual(g.host._responses,{})
    def test_outstanding_response_limit(self):
        g=Guest(NativeClient());g.memory.write(g.store,b'status',0);g.memory.write(g.store,b'{}',128)
        for _ in range(16):g.exports['request'](g.store,0,6,128,2)
        with self.assertRaises(wasmtime.Trap):g.exports['request'](g.store,0,6,128,2)
        g.host.close();self.assertEqual(g.host._responses,{})
    def test_closed_host_never_authorizes(self):
        c=NativeClient();g=Guest(c);g.host.close();g.host.close()
        with self.assertRaisesRegex(wasmtime.Trap,'closed'):g.call('require',{'module':'core'})
        self.assertEqual(c.calls,0)
    def test_released_handles_trap_and_are_not_reused(self):
        g=Guest(NativeClient());g.memory.write(g.store,b'status',0);g.memory.write(g.store,b'{}',128)
        token=g.exports['request'](g.store,0,6,128,2)
        g.exports['release'](g.store,token)
        with self.assertRaises(wasmtime.Trap):g.exports['read'](g.store,token,0,0,20)
        with self.assertRaises(wasmtime.Trap):g.exports['release'](g.store,token)
        g.host._next=2147483647
        last=g.exports['request'](g.store,0,6,128,2)
        self.assertEqual(last,2147483647)
        with self.assertRaisesRegex(wasmtime.Trap,'exhausted'):g.exports['request'](g.store,0,6,128,2)
        self.assertIn(last,g.host._responses)
        g.exports['release'](g.store,last)
    def test_exact_memory_bounds_and_negative_read_capacity(self):
        g=Guest(NativeClient());g.memory.write(g.store,b'status',0);g.memory.write(g.store,b'{}',128)
        length=g.memory.data_len(g.store)
        for pointer,size in [(length,1),(length-1,2),(0,-1),(0,LIMIT+1)]:
            with self.assertRaises(wasmtime.Trap):g.exports['request'](g.store,pointer,size,128,2)
        token=g.exports['request'](g.store,0,6,128,2)
        with self.assertRaises(wasmtime.Trap):g.exports['read'](g.store,token,0,0,-1)
        with self.assertRaises(wasmtime.Trap):g.exports['read'](g.store,token,0,0,0)
        with self.assertRaises(wasmtime.Trap):g.exports['read'](g.store,token,-1,0,16)
        self.assertGreater(g.exports['read'](g.store,token,0,length-16,16),0)
        g.exports['release'](g.store,token)
    def test_malformed_guest_json_fails_closed(self):
        c=NativeClient();g=Guest(c);g.memory.write(g.store,b'require',0)
        for raw in [b'[]',b'{',b'{"module":true}',b'\xff','{"module":"core"}'.encode('utf-16'),b'['*1500+b']'*1500]:
            g.memory.write(g.store,raw,128)
            token=g.exports['request'](g.store,0,7,128,len(raw))
            self.assertEqual(json.loads(g.host._responses[token]),{'ok':False,'error':'invalid_argument'})
            g.exports['release'](g.store,token)
        self.assertEqual(c.calls,0)
    def test_mutating_arguments_are_validated_before_native_call(self):
        class Client(NativeClient):
            def record(self,*args):self.calls+=1
        c=Client();g=Guest(c,allowed_operations=OPERATIONS)
        for elapsed in [-1,math.nan,math.inf,True]:
            self.assertEqual(g.call('record',{'command':'export','success':True,'elapsed':elapsed}),{'ok':False,'error':'invalid_argument'})
        self.assertEqual(c.calls,0)
        self.assertTrue(g.call('record',{'command':'export','success':True,'elapsed':0.125})['ok'])
        self.assertEqual(c.calls,1)
    def test_explicit_sign_in_timeout_host_policy(self):
        class Client(NativeClient):
            def sign_in(self,*,timeout):self.calls+=1;return timeout
        c=Client();g=Guest(c,allowed_operations={'sign_in'},sign_in_timeout=2)
        for timeout in [0,-1,3,True,math.nan,math.inf]:
            self.assertEqual(g.call('sign_in',{'timeout':timeout}),{'ok':False,'error':'invalid_argument'})
        self.assertEqual(c.calls,0)
        self.assertEqual(g.call('sign_in'),{'ok':True,'value':2})
    def test_host_faults_do_not_leak_details_or_authorize(self):
        class Client(NativeClient):
            def require(self,module):raise RuntimeError('synthetic-host-secret')
        g=Guest(Client())
        with self.assertRaises(wasmtime.Trap) as failure:g.call('require',{'module':'core'})
        self.assertNotIn('synthetic-host-secret',str(failure.exception))
        self.assertEqual(g.host._responses,{})
        self.assertFalse(g.host._busy)
    def test_response_limits_and_unserializable_native_results(self):
        class LargeClient(NativeClient):
            def status(self):return 'x'*(LIMIT+1)
        g=Guest(LargeClient())
        self.assertEqual(g.call('status'),{'ok':False,'error':'response_too_large'})
        class InvalidClient(NativeClient):
            def status(self):return object()
        g=Guest(InvalidClient())
        with self.assertRaisesRegex(wasmtime.Trap,'result invalid'):g.call('status')
        self.assertEqual(g.host._responses,{})
    def test_callback_reentry_and_close_reject_without_mutation(self):
        class Client(NativeClient):
            def require(self,module):
                with test.assertRaises(wasmtime.Trap):g.call('status')
                with test.assertRaises(RuntimeError):g.host.close()
                return {'modules':[module]}
        test=self;g=Guest(Client())
        self.assertTrue(g.call('require',{'module':'core'})['ok'])
        self.assertFalse(g.host._closed)
    def test_host_lifecycle_is_thread_confined_and_single_install(self):
        g=Guest(NativeClient());errors=[]
        def other_thread():
            try:g.host.close()
            except RuntimeError as error:errors.append(str(error))
        worker=threading.Thread(target=other_thread);worker.start();worker.join()
        self.assertEqual(errors,['host is thread confined'])
        self.assertTrue(g.call('status')['ok'])
        with self.assertRaises(RuntimeError):g.host.install(wasmtime.Linker(g.engine))
    def test_invalid_host_configuration(self):
        for timeout in [True,0,-1,math.inf,math.nan,'60']:
            with self.assertRaises(ValueError):Host(NativeClient(),sign_in_timeout=timeout)
        with self.assertRaises(ValueError):Host(NativeClient(),allowed_operations={'configure'})
    def test_guest_without_exported_memory_traps(self):
        c=NativeClient();engine=wasmtime.Engine();store=wasmtime.Store(engine)
        linker=wasmtime.Linker(engine);host=Host(c);host.install(linker)
        module=wasmtime.Module(engine,wasmtime.wat2wasm('(module (import "licensebox" "request" (func $r (param i32 i32 i32 i32) (result i32))) (func (export "run") (result i32) i32.const 0 i32.const 0 i32.const 0 i32.const 0 call $r))'))
        instance=linker.instantiate(store,module)
        with self.assertRaisesRegex(wasmtime.Trap,'export memory'):instance.exports(store)['run'](store)
        self.assertEqual(c.calls,0)
        host.close()
    def test_wasmtime_imports_retain_callback_host(self):
        g=Guest(NativeClient());reference=weakref.ref(g.host)
        del g.host;gc.collect()
        self.assertIsNotNone(reference())
        self.assertTrue(g.call('status')['ok'])
        reference().close()
    def test_partial_import_installation_fails_closed(self):
        engine=wasmtime.Engine();linker=wasmtime.Linker(engine);host=Host(NativeClient())
        i32=wasmtime.ValType.i32()
        linker.define_func('licensebox','read',wasmtime.FuncType([i32]*4,[i32]),lambda *_:0)
        with self.assertRaises(wasmtime.WasmtimeError):host.install(linker)
        self.assertTrue(host._closed)
        host.close()
if __name__=='__main__':unittest.main()
