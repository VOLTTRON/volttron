import logging
import os
import sys
import tempfile

import pytest

from volttron.platform.aip import AIPplatform
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.utils.utils import get_rand_vip


@pytest.fixture(scope='module')
def aip(request):
    volttron_home = tempfile.mkdtemp()
    packaged_dir = os.path.join(volttron_home, "packaged")
    os.makedirs(packaged_dir)
    ipc = 'ipc://{}{}/run/'.format(
        '@' if sys.platform.startswith('linux') else '',
        volttron_home)
    local_vip_address = ipc + 'vip.socket'
    os.environ['VOLTTRON_HOME'] = volttron_home

    opts = dict(
        volttron_home=volttron_home,
        vip_address=get_rand_vip(),
        local_vip_address=ipc+'vip.socket',
        publish_address=ipc+'publish',
        subscribe_address=ipc+'subscribe',
        log_level=logging.DEBUG
    )
    options = type('Options', (), opts)

    # 'verify_agents': False,
    # 'volttron_home': self.volttron_home,
    # 'vip_address': vip_address,
    # 'vip_local_address': ipc + 'vip.socket',
    # 'publish_address': ipc + 'publish',
    # 'subscribe_address': ipc + 'subscribe',
    # 'bind_web_address': bind_web_address,
    # 'volttron_central_address': volttron_central_address,
    # 'volttron_central_serverkey': volttron_central_serverkey,
    # 'platform_name': None,
    # 'log': os.path.join(self.volttron_home, 'volttron.log'),
    # 'log_config': None,
    # 'monitor': True,
    # 'autostart': True,
    # 'log_level': logging.DEBUG,
    # 'verboseness': logging.DEBUG
    aip = AIPplatform(options)
    aip.setup()
    return aip

