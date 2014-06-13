# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
# pylint: disable=W0142,W0403
#}}}

from setuptools import setup, find_packages


setup(
    name = 'volttron.restricted',
    version = '0.1',
    description = 'VOLTTRON license restricted components.',
    author = 'Volttron Team',
    author_email = 'bora@pnnl.gov',
    url = 'http://www.pnnl.gov',
    packages = find_packages(),
    install_requires = [],
    entry_points = '''
    [volttron.switchboard.resmon]
    platform = volttron.restricted.platform.resmon:ResourceMonitor
    ''',
    test_suite = 'nose.collector',
    zip_safe = True,
)
