from configparser import ConfigParser
import contextlib
import os
import shutil
from io import BytesIO
from mock import Mock

from volttrontesting.utils.platformwrapper import create_volttron_home


def get_test_web_env(path, input_data: bytes = None, query_string='', url_scheme='http', method='GET',):
    """
    Constructs the environment that gets passed to a wsgi application during a request
    from client to server.  The response will return a valid env that can be passed
    into the applications "run" path.

    :param path: the endpoint/file/websocket to call
    :param input_data:  input data to be passed into the request (must be a ByteIO object
    :param query_string: form or other data to be used as input to the environment.
    :param url_scheme: the scheme used to set the environment (http, https, ws, wss)
    :param method: REQUEST_METHOD used for this request (GET, POST, PUT etc)
    :return: A dictionary to be passed to the app_routing function in the masterwebservice
    """
    if path is None:
        raise ValueError("Invalid path specified.  Cannot be None.")
    byte_data = BytesIO()
    len_input_data = 0
    if input_data is not None:
        byte_data.write(input_data)
        byte_data.seek(0)
        len_input_data = len(input_data)

    if url_scheme not in ('http', 'https', 'ws', 'wss'):
        raise ValueError(f"Invalid url_scheme specified {url_scheme}")
    stdenvvars = {
        'SERVER_NAME': 'v2',
        'SERVER_PORT': '8080',
        'REQUEST_METHOD': method,
        # Replace the PATH_INFO in each test to customize the location/endpoint of
        # the functionality.
        'PATH_INFO': path,
        'QUERY_STRING': query_string,
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'REMOTE_ADDR': '192.168.56.101',
        'REMOTE_PORT': '44016',
        'HTTP_HOST': 'v2:8080',
        'HTTP_CONNECTION': 'keep-alive',
        'HTTP_CACHE_CONTROL': 'max-age=0',
        'HTTP_UPGRADE_INSECURE_REQUESTS':  '1',
        'HTTP_USER_AGENT': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36',
        'HTTP_ACCEPT': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'HTTP_ACCEPT_ENCODING': 'gzip, deflate',
        'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.9',
        'CONTENT_LENGTH': len_input_data,
        'wsgi.input': byte_data,  # input_data,  # {Input} <gevent.pywsgi.Input object at 0x7fd11882a588>
        'wsgi.input_terminated': True,
        'wsgi.url_scheme': url_scheme,
        "JINJA2_TEMPLATE_ENV": Mock()
        # ,
        # 'CONTENT_LENGTH': len(input_data.getvalue().decode('utf-8'))
    }

    return stdenvvars


@contextlib.contextmanager
def get_test_volttron_home(volttron_config_params: dict = None, volttron_home=None):
    if volttron_home is None:
        volttron_home = create_volttron_home()
    # Because we also can take in a volttron_home we want to make sure that
    # we have made the directory before going on.
    os.makedirs(volttron_home, exist_ok=True)
    original_home = os.environ.get('VOLTTRON_HOME')
    os.environ['VOLTTRON_HOME'] = volttron_home
    if volttron_config_params:
        config_path = os.path.join(volttron_home, "config")
        conf = ConfigParser()
        conf.add_section("volttron")
        for k, v in volttron_config_params.items():
            conf.set("volttron", k, v)
        with open(config_path, 'w') as fp:
            conf.write(fp)

    yield volttron_home

    if original_home is None:
        os.environ.unsetenv('VOLTTRON_HOME')
    else:
        os.environ['VOLTTRON_HOME'] = original_home
    shutil.rmtree(volttron_home, ignore_errors=True)
