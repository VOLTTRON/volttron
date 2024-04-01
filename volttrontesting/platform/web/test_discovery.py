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


import os

from volttron.platform.web import DiscoveryInfo
from volttrontesting.platform.web.test_web_authentication import skip_non_auth


def test_discovery_endpoint(volttron_instance_web):
    """
    Test that the correct discovery information is returned
    :param volttron_instance_web:
    :return:
        """
    skip_non_auth(volttron_instance_web)
    wrapper = volttron_instance_web

    # Both http and https start with http
    assert wrapper.bind_web_address.startswith('http')
    if wrapper.messagebus == 'rmq' or wrapper.bind_web_address.startswith('https'):
        os.environ['REQUESTS_CA_BUNDLE'] = wrapper.requests_ca_bundle

    info = DiscoveryInfo.request_discovery_info(wrapper.bind_web_address)

    assert wrapper.bind_web_address == info.discovery_address
    assert wrapper.serverkey == info.serverkey
    assert wrapper.messagebus == info.messagebus_type
    assert wrapper.instance_name == info.instance_name
    assert wrapper.vip_address == info.vip_address
    if wrapper.messagebus == 'rmq':
        ca_cert = wrapper.certsobj.ca_cert(public_bytes=True)
        assert ca_cert == info.rmq_ca_cert.encode('utf-8')
        print(ca_cert)
        print(info.rmq_ca_cert.encode('utf-8'))
