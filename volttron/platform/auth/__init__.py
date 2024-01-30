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

from volttron.platform.auth.auth import AuthService
from volttron.platform.auth.auth_entry import AuthEntry, AuthEntryInvalid
from volttron.platform.auth.auth_file import (
    AuthFile, AuthFileEntryAlreadyExists,
    AuthFileUserIdAlreadyExists, AuthFileIndexError
)
from volttron.platform.auth.auth_exception import AuthException
from volttron.platform.auth.certs import Certs, CertError, CertWrapper

__all__ = [ # Auth Service
            "AuthService",
            # Auth Entry 
            "AuthEntry", 
            "AuthEntryInvalid", 
            # Auth File
            "AuthFile", 
            "AuthFileEntryAlreadyExists", 
            "AuthFileUserIdAlreadyExists",
            "AuthFileIndexError"
            # Auth Exception
            "AuthException", 
            # Certs
            "Certs", 
            "CertError", 
            "CertWrapper"]
