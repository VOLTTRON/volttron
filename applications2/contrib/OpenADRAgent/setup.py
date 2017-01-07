#!/usr/bin/env python
from setuptools import setup, find_packages

packages = find_packages('.')
package = packages[0]

setup(
    name = package + 'agent',
    version = "0.1",
    description = 'OpenADR 2.0a agent for Volttron',
    author = 'EnerNOC Advanced Technology',
    author_email = 'tnichols@enernoc.com',
    url = 'http://open.enernoc.com',
    install_requires = ['volttron','oadr2-ven'],
    packages = packages,
    entry_points = {
        'setuptools.installation': [
            'eggsecutable = ' + package + '.agent:main',
        ]
    }
)
