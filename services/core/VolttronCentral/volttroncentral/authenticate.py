"""
    A simple authorization for authenticating users with known credentials.

    @author: Craig Allwardt
"""
import hashlib


class Authenticate:

    def __init__(self, user_map):
        """
        Expected usermap of
            user: {
                password: 'sha256password',
                groups: {
                    ['group1', 'group2']
                }
            }
        """
        self.users = user_map

    def authenticate(self, username, password):
        """ Authenticate that the user is known to the system.

        Return groups of the user if the user is known otherwise returns None.
        :param username:
        :param password:
        :return: list(groups) or None
        """
        if username in self.users.keys():
            # Do a naive hash of the user supplied password and if success return
            # the groups that the user holds.
            if self.users[username]['password'] == hashlib.sha512(password).hexdigest():
                return self.users[username]['groups']

        return None
