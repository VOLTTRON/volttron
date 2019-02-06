import re
import logging

from volttron.platform.agent import json
from volttron.platform.agent.utils import get_fq_identity
from volttron.platform.agent.web import Response
from volttron.platform.certs import Certs

_log = logging.getLogger(__name__)


class CSREndpoints(object):

    def __init__(self):
        self._certs = Certs()

    def get_routes(self):
        """
        Returns a list of tuples with the routes for authentication.

        :return:
        """
        return [
            (re.compile('^/csr/request_new$'), 'callable', self._csr_request_new)
        ]

    def _csr_request_new(self, env, data):

        if not isinstance(data, dict):
            try:
                request_data = json.loads(data)
            except:
                _log.error("Invalid data for csr request.  Must be json serializable")
                return Response()
        else:
            request_data = data.copy()

        csr = request_data.get('csr')
        identity = request_data.get('identity')

        instance_new_name = get_fq_identity(identity)

        csr_file = self._certs.csr_create_file(instance_new_name)
        if csr:
            with open(csr_file, "wb") as fw:
                fw.write(csr)

        auto_accept = True
        if auto_accept:
            cert = self._certs.sign_csr(csr_file)
            json_response = dict(
                status="SUCCESSFUL",
                cert=cert
            )
        else:
            json_response = dict(status="PENDING")

        return Response(json.dumps(json_response),
                        content_type='application/json',
                        headers={'Content-type': 'application/json'})

        # start_response('200 OK', [('Content-type', 'application/json')])
        # return jsonapi.dumps(json_response)
