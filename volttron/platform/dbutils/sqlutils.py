# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
import inspect
import logging

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


def get_dbfuncts_class(database_type):
    mod_name = database_type + "functs"
    mod_name_path = "volttron.platform.dbutils.{}".format(
        mod_name)
    loaded_mod = __import__(mod_name_path, fromlist=[mod_name])
    # loaded_mod = importlib.import_module(name=mod_name_path)
    for name, cls in inspect.getmembers(loaded_mod):
        # assume class is not the root dbdriver
        if inspect.isclass(cls) and name != 'DbDriver':
            dbfuncts_class = cls
            break
    try:
        _log.debug('Historian using module: ' + dbfuncts_class.__name__)
    except NameError:
        raise Exception('Invalid module named ' + mod_name_path + ".")
    return dbfuncts_class
