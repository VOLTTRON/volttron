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
import inspect
import logging

from volttron.platform.agent import utils
from volttron.platform.dbutils.basedb import DbDriver

utils.setup_logging()
_log = logging.getLogger(__name__)


def get_dbfuncts_class(database_type):
    mod_name = database_type + "functs"
    mod_name_path = "volttron.platform.dbutils.{}".format(mod_name)
    loaded_mod = __import__(mod_name_path, fromlist=[mod_name])
    for _, cls in inspect.getmembers(loaded_mod):
        # Ensure class is not the root dbdriver
        if (inspect.isclass(cls) and issubclass(cls, DbDriver)
                and cls is not DbDriver):
            break
    else:
        raise Exception('Invalid module named {}'.format(mod_name_path))
    _log.debug('Historian using module: {}'.format(cls.__name__))
    return cls
