import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.routes.mqtt_runtime_routes import MQTTConnectRequest, connect
import json
from starlette.responses import JSONResponse

# Valid printer (from DB)
req = MQTTConnectRequest(use_printer_config=True, printer_id='a8a51ff3-a44b-4825-969b-a5d545388140')
res = connect(req)
print('Valid printer result:')
if isinstance(res, JSONResponse):
    print(res.body.decode())
else:
    print(json.dumps(res, default=str))

# Missing printer_id
req2 = MQTTConnectRequest(use_printer_config=True)
res2 = connect(req2)
print('\nMissing printer_id result:')
if isinstance(res2, JSONResponse):
    print(res2.body.decode())
else:
    print(json.dumps(res2, default=str))

# Manual connect (will likely fail to reach broker but should pass validation)
req3 = MQTTConnectRequest(broker='127.0.0.1', port=1883, client_id='fh_test', username='u', password='p', tls=False, protocol='3.1.1')
res3 = connect(req3)
print('\nManual connect result:')
if isinstance(res3, JSONResponse):
    print(res3.body.decode())
else:
    print(json.dumps(res3, default=str))
