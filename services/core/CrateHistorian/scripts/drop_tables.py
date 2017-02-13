from crate import client
import os
from zmq.utils import jsonapi

root = os.path.dirname(os.path.abspath(__file__))
with open('{}/crate_config'.format(root), 'r') as fp:
    data = jsonapi.loads(fp.read())

host = data['connection']['params']['host']
conn = client.connect(host, error_trace=True)

cursor = conn.cursor()

schema = ''
tables = ['analysis', 'analysis_double',
          'datalogger', 'datalogger_double',
          'device', 'device_double', 'topic',
          'meta', 'record']

for t in tables:
    try:
        if schema:
            full_table_name = "{schema}.{table}".format(schema=schema,
                                                        table=t)
        else:
            full_table_name = t

        cursor.execute("DROP TABLE {}".format(full_table_name))
    except Exception as ex:
        print(ex.message)

cursor.close()
conn.close()