import base64
import warnings

from volttron.platform import jsonapi
from werkzeug.wrappers import Response as WerkResponse


class Response(WerkResponse):
    """ The WebResponse object is a serializable representation of
    a response to an http(s) client request that can be transmitted
    through the RPC subsystem to the appropriate platform's MasterWebAgent
    """

    def __init__(self, content=None, status=None,  headers=None, mimetype=None,
                 content_type=None):
        if content_type is None:
            content_type = 'text/html'
        super(Response, self).__init__(response=content, status=status, headers=headers, content_type=content_type,
                                 mimetype=mimetype)
        self._content = content

    @property
    def content(self):
        warnings.warn("This property should not be used any longer, please use .response instead.",
                      DeprecationWarning)
        ret_value = self._content
        # If user wants json then change it to json.
        if self._contenttype == 'application/json':
            assert isinstance(self._content, dict) or isinstance(self._content, list), \
                "Dictionary or list required for content-type dictionary"
            ret_value = jsonapi.dumpb(self._content)

        return ret_value

    def add_header(self, key, value):
        self.headers.add(key, value)

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
