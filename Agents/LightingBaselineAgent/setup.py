#!/usr/bin/env python
from setuptools import setup, find_packages

packages = find_packages('.')
package = packages[0]

setup(
    name = package + 'agent',
    version = "0.1",
    description = 'Lighting load analysis agent for Volttron',
    url = 'https://bitbucket.org/berkeleylab/eetd-volttron-agents',
    install_requires = ['volttronlite','lighting_baseline'],
    packages = packages,
    entry_points = {
        'setuptools.installation': [
            'eggsecutable = ' + package + '.agent:main',
        ]
    }
)
