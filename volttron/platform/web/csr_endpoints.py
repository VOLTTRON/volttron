import re
import logging
import weakref

from volttron.platform.agent import json
from volttron.platform.agent.utils import get_platform_instance_name
from volttron.platform.agent.web import Response
from volttron.platform.certs import Certs

_log = logging.getLogger(__name__)


class CSREndpoints(object):

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

    def _csr_request_new(self, env, data):

        _log.debug("New csr request")
        if not isinstance(data, dict):
            try:
                request_data = json.loads(data)
            except:
                _log.error("Invalid data for csr request.  Must be json serializable")
                return Response()
        else:
            request_data = data.copy()

        csr = request_data.get('csr')
        identity = self._certs.get_csr_common_name(str(csr))

        # The identity must start with the current instances name or it is a failure.
        if not identity.startswith(get_platform_instance_name() + "."):
            json_response = dict(status="ERROR",
                                 message="CSR must start with instance name: {}".format(
                                     get_platform_instance_name()))
            Response(json.dumps(json_response),
                     content_type='application/json',
                     headers={'Content-type': 'application/json'})

        self._certs.save_pending_csr_request(env.get('REMOTE_ADDR'), identity, csr)

        auto_accept = False
        if auto_accept:
            if self._certs.cert_exists(identity, True):
                cert = self._certs.cert(identity, True)
            _log.debug("Creating cert and permissions for user: {}".format(identity))
            permissions = self._core().rmq_mgmt.get_default_permissions(identity)
            self._core().rmq_mgmt.create_user_with_permissions(identity,
                                                               permissions,
                                                               True)
            cert = self._certs.sign_csr(csr_file)
            json_response = dict(
                status="SUCCESSFUL",
                cert=cert
            )
        else:

            status = self._certs.get_csr_status(identity)
            cert = self._certs.get_cert_from_csr(identity)

            json_response = dict(status=status)
            if status == "APPROVED":
                json_response['cert'] = self._certs.get_cert_from_csr(identity)
            elif status == "PENDING":
                json_response['message'] = "The request is pending admininstrator approval."
            elif status == "UNKNOWN":
                json.response['message'] = "An unknown common name was specified to the server {}".format(identity)
            else:
                json_response['message'] = "An unkonwn error has occured during the respons phase"
                _
        return Response(json.dumps(json_response),
                        content_type='application/json',
                        headers={'Content-type': 'application/json'})
