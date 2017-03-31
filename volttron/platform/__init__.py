# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


""" Core package."""


import os
import psutil
import sys

__version__ = '4.1'


def set_home(home=None):
    """ Set the home directory with user and variables expanded.

    If the home is sent in, it used.
    Otherwise, the default value of '~/.volttron' is used.
    """
    os.environ["VOLTTRON_HOME"] = home or get_home()
    

def get_home():
    """ Return the home directory with user and variables expanded.

    If the VOLTTRON_HOME environment variable is set, it used.
    Otherwise, the default value of '~/.volttron' is used.
    """
    return os.path.abspath(
        os.path.normpath(
            os.path.expanduser(
                os.path.expandvars(
                    os.environ.get('VOLTTRON_HOME', '~/.volttron')))))


def get_address():
    """Return the VIP address of the platform
    If the VOLTTRON_VIP_ADDR environment variable is set, it used.
    Otherwise, it is derived from get_home()."""
    address = os.environ.get('VOLTTRON_VIP_ADDR')
    if not address:
        abstract = '@' if sys.platform.startswith('linux') else ''
        address = 'ipc://%s%s/run/vip.socket' % (abstract, get_home())

    return address


def get_volttron_root():
    """
    Returns the root folder where the volttron code base resideds on disk.

    :return: absolute path to root folder
    """
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )


def is_instance_running(volttron_home=None):
    from zmq.utils import jsonapi

    if volttron_home is None:
        volttron_home = get_home()

    instance_file = os.path.expanduser("~/.volttron_instances")
    if not os.path.isfile(instance_file):
        return False

    with open(instance_file, 'r') as fp:
        jsonobj = jsonapi.loads(fp.read())

    if volttron_home not in jsonobj:
        return False

    obj = jsonobj[volttron_home]
    pid = obj.get('pid', None)

    if not pid:
        return False

    return psutil.pid_exists(pid)
