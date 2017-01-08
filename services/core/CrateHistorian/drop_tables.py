from crate import client

conn = client.connect('localhost:4200', error_trace=True)

cursor = conn.cursor()

tables = ['analysis', 'datalogger', 'device', 'meta', 'record', 'topic']

for t in tables:
    cursor.execute("DROP TABLE {}".format(t))

cursor.close()
conn.close()