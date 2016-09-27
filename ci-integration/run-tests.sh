#!/bin/sh

export CI=travis
export FAST_FAIL=1

# The context should already have been activated at this point.

#pip install pymongo pytest pytest-bdd pytest-cov
pip install mock
pip install pytest pytest-timeout

exit_code=0

# Break up the tests to work around the issue in #754. Breaking them up allows 
# the files to be closed with the individual pytest processes
py.test -v docs
tmp_code=$?
exit_code=$tmp_code
echo $exit_code
if [ $tmp_code -ne 0 ]; then
  if [ $tmp_code -ne 5 ]; then
    if [ ${FAST_FAIL} ]; then
      echo "Fast failing!"
      exit $tmp_code
    fi
  fi
fi

py.test -v examples
tmp_code=$?
if [ $tmp_code -ne 0 ]; then
  if [ $tmp_code -ne 5 ]; then
    if [ ${FAST_FAIL} ]; then
      echo "Fast failing!"
      exit $tmp_code
    fi
    exit_code=$tmp_code
  fi
fi

py.test -v scripts
tmp_code=$?
if [ $tmp_code -ne 0 ]; then
  if [ $tmp_code -ne 5 ]; then
    if [ ${FAST_FAIL} ]; then
      echo "Fast failing!"
      exit $tmp_code
    fi
    exit_code=$tmp_code
  fi
fi

for D in services/core/*; do
    if [ -d "${D}" ]; then
        py.test -v ${D}
        tmp_code=$?
        if [ $tmp_code -ne 0 ]; then
          if [ $tmp_code -ne 5 ]; then
            if [ ${FAST_FAIL} ]; then
              echo "Fast failing!"
              exit $tmp_code
            fi
            exit_code=$tmp_code
          fi
        fi
    fi
done

py.test -v volttron
tmp_code=$?
if [ $tmp_code -ne 0 ]; then
  if [ $tmp_code -ne 5 ]; then
    if [ ${FAST_FAIL} ]; then
      echo "Fast failing!"
      exit $tmp_code
    fi
    exit_code=$tmp_code
  fi
fi

for D in volttrontesting/*; do
    if [ -d "${D}" ]; then
        py.test -v ${D}
        tmp_code=$?
        if [ $tmp_code -ne 0 ]; then
          if [ $tmp_code -ne 5 ]; then
            if [ ${FAST_FAIL} ]; then
              echo "Fast failing!"
              exit $tmp_code
            fi
            exit_code=$tmp_code
          fi
        fi
    fi
done

exit $exit_code

