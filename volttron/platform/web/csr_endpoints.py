import re
import logging
import weakref

from volttron.platform import jsonapi
from volttron.platform.agent.utils import get_platform_instance_name
from volttron.platform.agent.web import Response
from volttron.platform.auth.certs import Certs

_log = logging.getLogger(__name__)


class CSREndpoints:

    def __init__(self, core):
        self._core = weakref.ref(core)
        self._certs = Certs()

    def get_routes(self):
        """
        Returns a list of tuples with the routes for authentication.

        Tuple should have the following:

            - regular expression for calling the endpoint
            - 'callable' keyword specifying that a method is being specified
            - the method that should be used to call when the regular expression matches

        code:

            return [
                (re.compile('^/csr/request_new$'), 'callable', self._csr_request_new)
            ]

        :return:
        """
        return [
            (re.compile('^/csr/request_new$'), 'callable', self._csr_request_new)
        ]

    @staticmethod
    def _error_response(message):
        """Build the JSON error response returned for a rejected CSR request.

        :param message: reason shown to the caller
        :return: werkzeug Response with status ERROR
        """
        return Response(jsonapi.dumps(dict(status="ERROR", message=message)),
                        content_type='application/json',
                        headers={'Content-type': 'application/json'})

    def _csr_request_new(self, env, data):
        _log.debug("New csr request")
        if not isinstance(data, dict):
            try:
                request_data = jsonapi.loads(data)
            except:
                _log.error("Invalid data for csr request.  Must be json serializable")
                return self._error_response("Invalid data for csr request.  Must be json serializable")
        else:
            request_data = data.copy()

        csr = request_data.get('csr') if isinstance(request_data, dict) else None
        if not isinstance(csr, str) or not csr:
            _log.error("Invalid data for csr request.  Missing csr")
            return self._error_response("Invalid data for csr request.  The csr field is required")
        csr = csr.encode("utf-8")
        identity = self._certs.get_csr_common_name(csr)

        # The identity must start with the current instances name or it is a failure.
        if not identity.startswith(get_platform_instance_name() + "."):
            json_response = dict(status="ERROR",
                                 message="CSR must start with instance name: {}".format(
                                     get_platform_instance_name()))
            return Response(jsonapi.dumps(json_response),
                            content_type='application/json',
                            headers={'Content-type': 'application/json'})

        # Every request is recorded as pending.  Approval is an administrator
        # action performed through the auth service (``vctl auth approve`` or
        # the admin web UI); this endpoint never signs a CSR on its own.
        try:
            self._certs.save_pending_csr_request(env.get('REMOTE_ADDR'), identity, csr)
        except ValueError as err:
            # The common name passed the instance-name prefix check but is not a safe file name.
            _log.error("Refused csr request: %s", err)
            return self._error_response(str(err))

        status = self._certs.get_csr_status(identity)

        json_response = dict(status=status)
        if status == "APPROVED":
            json_response['cert'] = self._certs.get_cert_from_csr(identity)
        elif status == "PENDING":
            json_response['message'] = "The request is pending administrator approval."
        elif status == "DENIED":
            json_response['message'] = "The request has been denied by the administrator."
        elif status == "UNKNOWN":
            json_response['message'] = "An unknown common name was specified to the server {}".format(identity)
        else:
            json_response['message'] = "An unknown error has occurred during the response phase"

        response = None
        try:
            if json_response.get('cert', None):
                json_response['cert'] = json_response['cert'].decode('utf-8')
            response = Response(jsonapi.dumps(json_response),
                     content_type='application/json',
                     headers={'Content-type': 'application/json'})
        except BaseException as e:
            _log.error(f"Exception creating Response {e}")
        return response
