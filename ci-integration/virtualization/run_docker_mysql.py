import docker
from mysql import connector

# client = docker.from_env()
#
# container = client.containers.run('mysql:5.7', detach=True, auto_remove=True,
#                                   ports={3306:3306}, environment={'MYSQL_ROOT_PASSWORD': 'test'})
#
# print(container.id)
#
create_tables_file = "services/core/SQLHistorian/mysql-create.sql"

with open(create_tables_file) as fp:
    data = fp.read() # .split(";")


# conn_params = {
#     "host": "localhost",
#     "port": 3306,
#     "database": "test_historian",
#     "user": "historian",
#     "passwd": "historian"
# }

conn_params = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "passwd": "test",
    "auth_plugin": "mysql_native_password"
    # ,
    # "auth_plugin": "mysql_native_password"
}

conn = connector.connect(host="localhost", user="root", passwd="test") # , auth_plugin="mysql_native_password")
cursor = conn.cursor(buffered=True)
cursor.execute(data, multi=True)
# for d in data:
#     print(d)
#     cursor.execute(d)


cursor.close()
conn.close()
