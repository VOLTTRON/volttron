from crate import client
import os
from zmq.utils import jsonapi

root = os.path.dirname(os.path.abspath(__file__))
with open('{}/crate_config'.format(root), 'r') as fp:
    data = jsonapi.loads(fp.read())

host = data['connection']['params']['host']
conn = client.connect(host, error_trace=True)

cursor = conn.cursor()

tables = ['analysis', 'analysis_double',
          'datalogger', 'datalogger_double',
          'device', 'device_double',
          'meta', 'topic',
          'meta', 'record']

for t in tables:
    try:
        cursor.execute("DROP TABLE historian.{}".format(t))
    except Exception as ex:
        print(ex.message)

cursor.close()
conn.close()