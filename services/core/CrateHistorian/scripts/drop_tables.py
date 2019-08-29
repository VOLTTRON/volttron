from crate import client
import os
from volttron.platform import jsonapi

root = os.path.dirname(os.path.abspath(__file__))
with open('{}/crate_config'.format(root), 'r') as fp:
    data = jsonapi.loads(fp.read())

host = data['connection']['params']['host']
conn = client.connect(host, error_trace=True)

cursor = conn.cursor()

schema = 'test_import'
tables = ['analysis', 'analysis_string',
          'datalogger', 'datalogger_string',
          'device', 'device_string', 'topic',
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
        print(ex)

cursor.close()
conn.close()