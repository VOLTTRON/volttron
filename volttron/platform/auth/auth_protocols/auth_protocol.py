# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import volttron.platform
from volttron.platform import jsonapi

#BaseAuthorization class
class BaseServerAuthorization:
    def __init__(self,
                 auth_service=None
                 ):
        self.auth_service = auth_service

    def approve_authorization(self, user_id):
        pass

    def deny_authorization(self, user_id):
        pass

    def delete_authorization(self, user_id):
        pass

    def get_authorization(self, user_id):
        pass

    def get_authorization_status(self, user_id):
        pass

    def get_pending_authorizations(self):
        pass

    def get_approved_authorizations(self):
        pass

    def get_denied_authorizations(self):
        pass

    def update_user_capabilites(self, user_to_caps):
        pass

    def load_protected_topics(self, protected_topics_data):
        return jsonapi.loads(protected_topics_data) if protected_topics_data else {}

    def update_protected_topics(self, protected_topics):
        pass


class BaseClientAuthorization:
    def __init__(self, auth_service=None):
        self.auth_service = auth_service


# BaseAuthentication class
class BaseAuthentication:
    def __init__(self):
        pass

    def create_authentication_parameters(self):
        """
        Used to create an authenticated address
        based on authentication protocol and message bus.
        """
        pass


class BaseServerAuthentication(BaseAuthentication):
    def __init__(self, auth_service=None) -> None:
        super(BaseServerAuthentication, self).__init__()
        self.auth_service = auth_service
        self.authorization = None

    def setup_authentication(self):
        pass

    def handle_authentication(self, protected_topics):
        pass

    def stop_authentication(self):
        pass

    def unbind_authentication(self):
        pass
