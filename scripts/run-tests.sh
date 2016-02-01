#!/bin/sh

export CI=travis

# The context should already have been activated at this point.

#pip install pymongo pytest pytest-bdd pytest-cov
pip install mock
pip install pytest pytest-bdd pytest-cov
py.test -s -v
