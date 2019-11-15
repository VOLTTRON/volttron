import Cookie
import logging
from urlparse import urlparse
from volttron.platform.certs import Certs
from volttron.platform.agent.known_identities import MASTER_WEB
from volttron.platform.agent.utils import get_fq_identity

try:
    import jwt
except ImportError:
    logging.getLogger().warning("Missing library jwt within web package.")

from discovery import DiscoveryInfo, DiscoveryError

# Used outside so we make it available through this file.
from master_web_service import MasterWebService

_log = logging.getLogger(__name__)


class NotAuthorized(Exception):
    pass


def get_bearer(env):

    # Test if HTTP_AUTHORIZATION header is passed
    http_auth = env.get('HTTP_AUTHORIZATION')
    if http_auth:
        auth_type, bearer = http_auth.split(' ')
        if auth_type.upper() != 'BEARER':
            raise NotAuthorized("Invalid HTTP_AUTHORIZATION header passed, must be Bearer")
    else:
        cookiestr = env.get('HTTP_COOKIE')
        if not cookiestr:
            raise NotAuthorized()
        cookie = Cookie.SimpleCookie(cookiestr)
        bearer = cookie.get('Bearer').value.decode('utf-8')
    return bearer


def get_user_claims(env):
    bearer = get_bearer(env)
    return jwt.decode(bearer, env['WEB_PUBLIC_KEY'], algorithms='RS256')


def get_user_claim_from_bearer(bearer):
    certs = Certs()
    pubkey = certs.get_cert_public_key(get_fq_identity(MASTER_WEB))
    return jwt.decode(bearer, pubkey, algorithms='RS256')



def build_vip_address_string(vip_root, serverkey, publickey, secretkey):
    """ Build a full vip address string based upon the passed arguments

    All arguments are required to be non-None in order for the string to be
    created successfully.

    :raises ValueError if one of the parameters is None.
    """
    _log.debug("root: {}, serverkey: {}, publickey: {}, secretkey: {}".format(
        vip_root, serverkey, publickey, secretkey))
    parsed = urlparse(vip_root)
    if parsed.scheme == 'tcp':
        if not (serverkey and publickey and secretkey and vip_root):
            raise ValueError("All parameters must be entered.")

        root = "{}?serverkey={}&publickey={}&secretkey={}".format(
            vip_root, serverkey, publickey, secretkey)

    elif parsed.scheme == 'ipc':
        root = vip_root
    else:
        raise ValueError('Invalid vip root specified!')

    return root

