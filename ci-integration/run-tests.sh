#!/bin/sh

export CI=travis

# The context should already have been activated at this point.

#pip install pymongo pytest pytest-bdd pytest-cov
pip install mock
pip install pytest pytest-timeout

py.test -v docs
py.test -v examples
py.test -v scripts
for D in services/core/*; do
    if [ -d "${D}" ]; then
        py.test -v ${D}
    fi
done
py.test -v volttron
py.test -v volttrontesting
