#!/usr/bin/env python
from setuptools import setup, find_packages

packages = find_packages('.')
package = packages[0]

setup(
    name = package + 'agent',
    version = "0.1",
    description = 'Cumulative Sum agent for Volttron',
    url = 'https://bitbucket.org/berkeleylab/eetd-volttron-agents',
    install_requires = ['volttron','loadshape'],
    packages = packages,
    entry_points = {
        'setuptools.installation': [
            'eggsecutable = ' + package + '.agent:main',
        ]
    }
)
