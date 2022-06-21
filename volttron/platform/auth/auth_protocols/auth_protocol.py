# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import os
import volttron.platform
from volttron.platform import jsonapi

#BaseAuthorization class
class BaseServerAuthorization:
    def __init__(self,
                 auth_core=None
                 ):
        self.auth_core = auth_core
        
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
    def __init__(self, owner=None, core=None):
        self._owner = owner
        self._core = core

    def connect_remote_platform(self):
        pass


# BaseAuthentication class
class BaseAuthentication:
    def __init__(self):
        pass

    def create_authenticated_address(self):
        """
        Used to create an authenticated address
        based on authentication protocol and message bus.
        """
        pass


class BaseServerAuthentication(BaseAuthentication):
    def __init__(self) -> None:
        self.authorization = None
        self.auth_vip = None
        self.auth_core = None

    def setup_authentication(self):
        pass

    def handle_authentication(self, protected_topics):
        pass

    def stop_authentication(self):
        pass

    def unbind_authentication(self):
        pass
