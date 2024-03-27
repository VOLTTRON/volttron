from pathlib import Path
from requests import Session
import yaml

from ieee_2030_5 import xml_to_dataclass

__test_config_file__ = Path(__file__).parent.joinpath("fixtures/test_config.yml")
__test_config_file_data__ = yaml.safe_load(__test_config_file__.open("rt").read())

__request_admin_session__ = Session()
__request_base_uri__ = f"https://{__test_config_file_data__['server_hostname']}:{__test_config_file_data__['server_ssl_port']}"
__tls_path__ = Path(__test_config_file_data__["certfile"]).expanduser().parent.parent
__request_admin_session__.cert = (__tls_path__.joinpath("certs/admin.crt"), __tls_path__.joinpath("private/admin.pem"))
__request_admin_session__.verify = Path(__test_config_file_data__["cacertfile"]).expanduser().as_posix()

__request_device_session__ = Session()
__request_device_session__.cert = (__tls_path__.joinpath("certs/dev1.crt"), __tls_path__.joinpath("private/dev1.pem"))
__request_device_session__.verify = Path(__test_config_file_data__["cacertfile"]).expanduser().as_posix()
    
def __admin_uri__(path: str):
    path = path.replace("_", "/")
    if path.startswith("/"):
        path = path[1:]
    return f"{__request_base_uri__}/admin/{path}"

def __uri__(path: str):
    if path.startswith("/"):
        path = path[1:]
    return f"{__request_base_uri__}/{path}"

def post_as_admin(path, data):
    print(f"POST: {__admin_uri__(path)}")
    return __request_admin_session__.post(__admin_uri__(path), data=data)

def post_as_device(path, data):
    print(f"POST: {__uri__(path)}")
    return __request_device_session__.post(__uri__(path), data=data)


def get_as_admin(path) -> str:
    print(f"GET: {__uri__(path)}")
    resp = __request_device_session__.get(__admin_uri__(path))
    
    if resp.text:
        return xml_to_dataclass(resp.text)
    else:
        resp

def get_as_device(path) -> str:
    print(f"GET: {__uri__(path)}")
    resp = __request_device_session__.get(__uri__(path))
    
    if resp.text:
        return xml_to_dataclass(resp.text)
    else:
        resp