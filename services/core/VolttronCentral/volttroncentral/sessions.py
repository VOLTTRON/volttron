import errno
import os
from copy import deepcopy

class SessionHandler:
    """A cache of sessions authenticated by the platform web login.

    Callers add a session with `_add_session` once the platform has
    confirmed a login; this class does not authenticate on its own. A
    session token is stored with the user's ip address so later requests
    can be matched back to the ip they were issued to.
    """
    def __init__(self):
        self._sessions = {}
        self._session_tokens = {}
        self._stored_session_path = None

    def clear(self):
        self._sessions.clear()
        self._session_tokens.clear()

    def _add_session(self, user, token, ip, groups):
        """Add a user session to the session cache"""
        self._sessions[user] = {'user': user, 'token': token, 'ip': ip,
                                'groups': groups}
        self._session_tokens[token] = self._sessions[user]

    def check_session(self, token, ip):
        """Check if a user token has been authenticated.

        @return:
            A users session information or False.
        """
        if not self._session_tokens:
            self._load_auths()
        session = self._session_tokens.get(str(token))
        if session:
            if session['ip'] != ip:
                return False
            return deepcopy(session)

        return False

    def _store_session(self):
        # Disable the storing of sessions to disk.
        return
        # if not self._stored_session_path:
        #     self._get_auth_storage()
        #
        # with open(self._stored_session_path, 'wb') as file:
        #     file.write(jsonapi.dumps(self._sessions))

    def _load_auths(self):
        self._sessions = {}
        return
        #
        # if not self._stored_session_path:
        #     self._get_auth_storage()
        # try:
        #     with open(self._stored_session_path) as file:
        #         self._sessions = jsonapi.loads(file.read())
        #
        #     self._session_tokens.clear()
        #     for k, v in self._sessions.items():
        #         self._session_tokens[v['token']] = v
        # except IOError:
        #     pass

    def _get_auth_storage(self):
        if not os.environ.get('VOLTTRON_HOME', None):
            raise ValueError('VOLTTRON_HOME environment must be set!')

        db_path = os.path.join(os.environ.get('VOLTTRON_HOME'),
                               'data/volttron.central.sessions')
        db_dir  = os.path.dirname(db_path)
        try:
            os.makedirs(db_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                raise
        self._stored_session_path = db_path
