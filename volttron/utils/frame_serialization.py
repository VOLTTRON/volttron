# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

from json import JSONDecodeError
import logging
from typing import List, Any
from zmq.sugar.frame import Frame
import struct

from volttron.platform import jsonapi

_log = logging.getLogger(__name__)


def deserialize_frames(frames: List[Frame]) -> List:
    decoded = []
    for x in frames:
        if isinstance(x, list):
            decoded.append(deserialize_frames(x))
        elif isinstance(x, int):
            decoded.append(x)
        elif isinstance(x, float):
            decoded.append(x)
        elif isinstance(x, bytes):
            decoded.append(x.decode('utf-8'))
        elif isinstance(x, str):
            decoded.append(x)
        elif x is not None:
            # _log.debug(f'x is {x}')
            if x == {}:
                decoded.append(x)
                continue
            try:
                d = x.bytes.decode('utf-8')
            except UnicodeDecodeError as e:
                _log.debug(e)
                decoded.append(x)
                continue
            try:
                decoded.append(jsonapi.loads(d))
            except JSONDecodeError:
                decoded.append(d)
    # _log.debug("deserialized: {}".format(decoded))
    return decoded


def serialize_frames(data: List[Any]) -> List[Frame]:
    frames = []

    # _log.debug("Serializing: {}".format(data))
    for x in data:
        try:
            if isinstance(x, list) or isinstance(x, dict):
                frames.append(Frame(jsonapi.dumps(x).encode('utf-8')))
            elif isinstance(x, Frame):
                frames.append(x)
            elif isinstance(x, bytes):
                frames.append(Frame(x))
            elif isinstance(x, int):
                frames.append(struct.pack("I", x))
            elif isinstance(x, float):
                frames.append(struct.pack("f", x))
            elif x is None:
                frames.append(Frame(x))
            else:
                frames.append(Frame(x.encode('utf-8')))
        except TypeError as e:
            import sys
            sys.exit(0)
        except AttributeError as e:
            import sys
            # _log.debug("Serializing: {}".format(data))
            sys.exit(0)
    return frames


