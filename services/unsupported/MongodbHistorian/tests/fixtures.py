# Module level variables
BASE_DEVICE_TOPIC = "devices/Building/LAB/Device"
BASE_ANALYSIS_TOPIC = "analysis/Economizer/Building/LAB/Device"
ALL_TOPIC = "{}/all".format(BASE_DEVICE_TOPIC)

mongo_platform = {
    "agentid": "mongodb-historian",
    "connection": {
        "type": "mongodb",
        "params": {
            "host": "localhost",
            "port": 27017,
            "database": "mongo_test",
            "user": "historian",
            "passwd": "historian",
            "authSource": "test"
        }
    }
}


def mongo_connection_string():
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'

    params = mongo_connection_params()
    if params.get('authSource'):
        mongo_conn_str = mongo_conn_str + '?authSource={authSource}'
    mongo_conn_str = mongo_conn_str.format(**params)
    return mongo_conn_str


def mongo_agent_config():
    return mongo_platform


def mongo_connection_params():
    global mongo_platform
    mongo_params = mongo_platform['connection']['params']
    return mongo_params
