import base64

from volttron.platform import jsonapi


class Response(object):
    """ The WebResponse object is a serializable representation of
    a response to an http(s) client request that can be transmitted
    through the RPC subsystem to the appropriate platform's MasterWebAgent
    """

    def __init__(self, content=None, status=None,  headers=None, mimetype=None,
                 content_type=None):
        self._content = content
        if self._content is None:
            self._content = ''
        self._status = status
        if not self._status:
            self._status = '200 OK'
        self._headers = headers
        if not self._headers:
            self._headers = {}
        self._mimetype = mimetype
        self._contenttype = content_type
        if not self._contenttype:
            self._contenttype = 'text/html'

    @property
    def status(self):
        return self._status

    @property
    def headers(self):
        cpy = self._headers.copy()
        values = [(k, v) for k, v in cpy.items()]
        values.append(('Content-Type', self._contenttype))
        return values

    @property
    def content(self):
        ret_value = self._content
        # If user wants json then change it to json.
        if self._contenttype == 'application/json':
            assert isinstance(self._content, dict) or isinstance(self._content, list), \
                "Dictionary or list required for content-type dictionary"
            ret_value = jsonapi.dumpb(self._content)

        return ret_value

    def add_header(self, key, value):
        if key in self._headers:
            raise ValueError("key {} already exists in header.".format(key))

        self._headers[key] = value

    def process_data(self, data):
        if type(data) == bytes:
            self.base64 = True
            data = base64.b64encode(data)
        elif type(data) == str:
            self.base64 = False
        else:
            raise TypeError("Response data is neither bytes nor string type")
        return data


class JsonResponse(Response):

    def __init__(self, content):
        super(JsonResponse, self).__init__(content=content, content_type="application/json")
