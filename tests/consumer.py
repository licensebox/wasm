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
    client=Client('demo',{'synthetic':'ed25519-mldsa65:A6EHv_POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbgBskJ2J1ZnAC5A6WhahxalHLyrs5Np9U8kswmC3vyjzuM5K47fXvZQ-j8x35JybT0vXygJlrzL1XgbsswQZ5TsRxcRPJ_0gcuItfpG4hGPb8_kMRob8LeLhK9y0lyyKkjuPDAjLxpCoCtt1WebJSVZVEVNHVwbGAHIZzcI44Q_9XERNHnhn1pd0VH4hRmvBhEWJd2e7wui09lnVTUx-Xea97WP893KrtB_zMeyMz3YXaqybb3vMYq4qxZUTtbQRDEZWdczummvKgzQUfoh69hLTG5Yv3W8AEcCWCA17C18GVD9SmDFKfoNP7PqdHT8cBMgF717QebmrCfwVD32fL4JK5VCb_7jt4N2qKpTnyZh8Ip1WOA5E__dO88mVrUFiipkbESzqwTnI0JSl7Hpm0zPN2yhnzAgz4ZvR7DNTtcy6tiPjhAcOnknUNj9_sn4cAd8tEWeTcQIGh3gYOJVJf8llFJK2J-W86kM9zLYALmzcPJLeZRm3RPotMAd7CbWgBHCwGEx7_R8xKQHSn_bIX4HPNoKu-JwDXSu0jSd9tQyJF82to_UDBkDc1IXtwfqkk6g0jm0Nc76iPSHEaGxNtRHocnZxojIDzx07wEHbA2HjwWBkCRkH4SfdGopWDOvbNmxkFjfy9y2nYZ5UT0jtJcwJa2gUwLtkHm-ScarVsmLqphuFqH-MZ073mC4vf-DbSNLjfDB9GLDac1oUzP8SkHo7Lbbfv3k0p8k_Qn_gS2IttdHQ9bZNSv-ui-qffQ19FPPyriWxXUjU44Jc8kuG_07xG6PGbdkGaevMm5HKzYRjNUZxpzged7AqcztVznoNcpVXKVXr5uROHh6vPaYg-jYlkImr5TU1irFrcwKO6EnNd837UeoauInGbViwSmc24tYJqJgIW6Fc1Vj9IjuwbyjPplnRXo7c6SX2NVWznxSiOk487vjiCogCRqdD6nFpZXNotB3xYOKMlyhmXq1n-wVJxcc34GIQ8oDdbKJyP0xXMRLxg4xbbYUlmE1HKk0BXN-bARK9_MtGiFJjjPOAFmvndD5xA1VjNyuUe6bblyS2ybn5FqkbSsufyTnvsjY9GVhVkA-BBJRKvNS0qIpJEDFHb7uscQAChPKhpeC2JU2B9Qy7KLRhzX9c1ru15ZHvBN0U1yv_ScNW4tn7SD20yipPpiG_THNZDbg1n76LpV-T4odFNJqgF51u3wb86ck1JNr4yZK7GwKu1Hso8iVcoK_67J5J5xUWC6YL0biy4_13aTKEi4bDUPs7ZT0dGc6KDfAXbYFw8X4TEElIT33XvE-RD6vgrBRQr2zDDeRfmbBNrZBMs222h_Ghc4byXS70O2ecZ8VIlKN1Rzj3llEskHkovohBdkS5K7POWPc7CVWpVXt7EFw7hEOQ48bu9s0Seo_Clyyy1xu3S1kO4WM1tkLIK55uaRTYcxX7IuvTPpep2M9wn0dUE9DyKnVQ72Ofjwn_DGlKdRz0DYA6Qb7n1l57HOYe8MH0hDRRM0u0_wRphYPMIGx1KU3L7tpo5uOL0hA6a1iPIkcKH28N3GLfoD0Xcf0-VC58cZl3UXxLGDBbTavvKADWWYVkl7kQK2UgHbS34bKExQHGRh4SAas0uOy7cZ6hqmw-1brz0MWqmj4rCBlmSo-fqLlBz3U-St20pwNZpAqufTPHbbyqbCy2U9iNpLpiU_hkMyoFag3oaXr0a8I2nFQFEZP7jzPKbcmmTsfyBFkd517XXkljyNY6R9zZFfKV8dv90tYYaoVHZ3BUhOFXUYoB65VkFoWPbyGtuMxQ4zgzNnxHlUNn6kLidcYJbLy1vqnyy7cZz05CbjYVp2B4CdipAmdyvq-WDieMg4DYbmyYW_YQJwM0pi2YaTCHqNVbcDrR3yl1Wlzonp6X-Cw2zLdqV_Vo0lw2vmUdbcHkh1ulWhFKZ6FX57JzUeMD7SmXtYHQQq1imNP_17CJX6T6i9c_2xH4KevUz9gQb7chPOuDL0MHlguSZXttGotPtCex09jf-6dFsE_Bje-9yF4jpdJozimIolygCsb876JdhsIL3tJ7AGFeAKnNysAphoAbkluhwqJq1s7MNThUqYLIzyrwfu4yDeduzAks8XhlA5XkdnHSmEphbqVc7-6eqGlcBD2NEtGCNXxnEr5u3vAKn6ngQW4ms_0WiVnX0pjOM-XKdBOhnJg-4VsLX28i67SRxPFtYmB3pSy9HadLihn-vHeD1dk0K9GNhJDDS-TMutxoXunggKLdNwBoLgUgadnUKg0imeyKqbFp5fZpE5BRwite4rVByOW7hGZKxaPZWuIGjCYI8T72RZ6YpzsRVUI83sMQ-XOsIxg19NX2qvasM1cxdyFFmGr2R8ve00Xaf5S0q-bpLeDqfKyHyM6UijkZ8BGT69_Ms5QN2z38FrJURuBcwOIyKJlvYSOTHuBJD3YX0R-NyzMhzY7lVlcb59WeKwfUSMDPkjqxS6kQfzMT-w6LbNfVp4ZYqJEYvcezwKm2Rd1zFFr7cGPzCzIxRFb9gvWIjM8QGe0H81Jqt5e3mbBajO1Ojsn73TA5yNdvk0KBwppJhJagr8S4B9w4cVE8xezoQ1a7yNi4asPGw'},directory=directory)
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
