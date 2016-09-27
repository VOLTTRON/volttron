#!/bin/sh

export CI=travis

# The context should already have been activated at this point.

#pip install pymongo pytest pytest-bdd pytest-cov
pip install mock
pip install pytest pytest-timeout

# Break up the tests to work around the issue in #754. Breaking them up allows 
# the files to be closed with the individual pytest processes
py.test -v docs
py.test -v examples
py.test -v scripts
for D in services/core/*; do
    if [ -d "${D}" ]; then
        py.test -v ${D}
    fi
done
py.test -v volttron

for D in volttrontesting/*; do
    if [ -d "${D}" ]; then
        py.test -v ${D}
    fi
done
