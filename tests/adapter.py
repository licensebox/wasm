import json,sys
from licensebox import Client,LicenseboxError,derive_binding,native_binding,verify_lease
from licensebox_wasm import OPERATIONS
from runtime import Guest
r=json.load(sys.stdin);op=r["op"]
try:
    # Native primitives execute exclusively in the host; guests never provide raw IDs.
    if op=="derive":result=derive_binding(r["product"],r["source"],r["raw_id"])
    elif op=="native":result=native_binding(r["product"])
    elif op=="verify":result=verify_lease(r["token"],r["product"],r["keys"],r["now"])
    else:
        c=Client(r["product"],r["keys"],server=r["server"],directory=r["directory"],version="conformance",clock=lambda:r["now"],machine_binding=lambda:r["binding"],on_sign_in=lambda *_:None)
        guest=Guest(c,allowed_operations=OPERATIONS)
        def call(name,args=None):
            value=guest.call(name,args)
            if not value["ok"]:raise LicenseboxError(value["error"])
            return value["value"]
        if op=="repeat":call("require",{"module":"core"});result=call("require",{"module":"core"})
        elif op=="record":call(op,{"command":"export","success":True,"elapsed":.125});result=call(op,{"command":"export","success":False,"elapsed":.025})
        elif op=="request":result=call(op,{"modules":["export"],"note":"café – test"})
        elif op=="require":result=call(op,{"module":r.get("module","core")})
        elif op=="sign_in":result=call(op,{"timeout":3})
        else:result=call(op)
        guest.host.close()
    print(json.dumps({"ok":True,"value":result}))
except LicenseboxError as e:print(json.dumps({"ok":False,"error":e.code}))
