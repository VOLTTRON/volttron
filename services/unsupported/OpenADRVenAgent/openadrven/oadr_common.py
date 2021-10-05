HTTP_STATUS_CODES = {200: '200 OK',
                     201: '201 Created',
                     204: '204 No Content',
                     500: '500 Internal Error'}

# OADR Response Codes
OADR_VALID_RESPONSE = '200'
OADR_MOD_NUMBER_OUT_OF_ORDER = '450'
OADR_BAD_DATA = '459'
OADR_BAD_SIGNAL = '460'
OADR_EMPTY_DISTRIBUTE_EVENT = '999'

SCHEMA_VERSION = '2.0b'


class OpenADRException(Exception):
    """Abstract superclass for exceptions in the Open ADR VEN agent."""

    def __init__(self, message, error_code, *args):
        super(OpenADRException, self).__init__(message, *args)
        self.error_code = error_code


class OpenADRInterfaceException(OpenADRException):
    """Use this exception when an error should be sent to the VTN as an OadrResponse payload."""

    def __init__(self, message, error_code, *args):
        super(OpenADRInterfaceException, self).__init__(message, error_code, *args)


class OpenADRInternalException(OpenADRException):
    """Use this exception when an error should be logged but not sent to the VTN."""

    def __init__(self, message, error_code, *args):
        super(OpenADRInternalException, self).__init__(message, error_code, *args)
