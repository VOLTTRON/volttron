import pytest
from influxdb import InfluxDBClient

influxdb_config = {
    "connection": {
        "params": {
            "host": "localhost",
            "port": 8086,
            "database": "historian",
            "user": "admin",
            "passwd": "admin"
        }
    },
    "aggregations": {
        "use_calendar_time_periods": True
    }
}

influxdb_config_without_calender_period = {
    "connection": {
        "params": {
            "host": "localhost",
            "port": 8086,
            "database": "historian",
            "user": "admin",
            "passwd": "admin"
        }
    },
    "aggregations": {
        "use_calendar_time_periods": False
    }
}

updated_influxdb_config = {
    "connection": {
        "params": {
            "host": "localhost",
            "port": 8086,
            "database": "updated-historian",
            "user": "admin",
            "passwd": "admin"
        }
    }
}


expected_table_list = [
    u'data',
    u'meta',
]

DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

query_topics = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}

long_topics = [
    "CampusA/Building1/LAB1/Device1/OutsideAirTemperature",
    "CampusB/Building2/LAB2/Device2/DamperSignal",
]

short_topics = [
    "LAB1/Device1/OutsideAirTemperature",
    "LAB2/Device2/DamperSignal",
]


@pytest.fixture(scope="function")
def influxdb_client():
    host = influxdb_config['connection']['params']['host']
    port = influxdb_config['connection']['params']['port']
    user = influxdb_config['connection']['params']['user']
    passwd = influxdb_config['connection']['params']['passwd']
    db = influxdb_config['connection']['params']['database']

    client = InfluxDBClient(host, port, user, passwd, db)
    return client


