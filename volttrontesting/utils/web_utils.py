from io import BytesIO

from mock import Mock


def get_test_web_env(path, input_data: bytes = None, query_string='', url_scheme='http', method='GET',
                     **kwargs) -> dict:
    """
    Constructs the environment that gets passed to a wsgi application during a request
    from client to server.  The response will return a valid env that can be passed
    into the applications "run" path.

    :param path: the endpoint/file/websocket to call
    :param input_data:  input data to be passed into the request (must be a ByteIO object)
    :param query_string: form or other data to be used as input to the environment.
    :param url_scheme: the scheme used to set the environment (http, https, ws, wss)
    :param method: REQUEST_METHOD used for this request (GET, POST, PUT etc)

    :return: A dictionary to be passed to the app_routing function in the platformwebservice
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
        'HTTP_UPGRADE_INSECURE_REQUESTS': '1',
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

    # Use kwargs passed and add them to the stdvars and make them available
    # in the environment.
    for k, v in kwargs.items():
        stdenvvars[k] = v

    return stdenvvars
