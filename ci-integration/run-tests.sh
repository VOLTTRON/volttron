#!/bin/sh

export CI=travis

# The context should already have been activated at this point.

#pip install pymongo pytest pytest-bdd pytest-cov
pip install mock
pip install pytest pytest-timeout

exit_code=0

# Break up the tests to work around the issue in #754. Breaking them up allows 
# the files to be closed with the individual pytest processes
py.test -v docs
if [ $? != 0 ]; then
  exit_code=$?
fi

py.test -v examples
if [ $? != 0 ]; then
  exit_code=$?
fi

py.test -v scripts
if [ $? != 0 ]; then
  exit_code=$?
fi

p
for D in services/core/*; do
    if [ -d "${D}" ]; then
        py.test -v ${D}
        if [ $? != 0 ]; then
            exit_code=$?
        fi
    fi
done
py.test -v volttron
if [ $? != 0 ]; then
  exit_code=$?
fi

for D in volttrontesting/*; do
    if [ -d "${D}" ]; then
        py.test -v ${D}
        if [ $? != 0 ]; then
            exit_code=$?
        fi
    fi
done

exit $exit_code
