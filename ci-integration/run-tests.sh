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

# testdirs=("examples" "services/core/*" "volttron" "volttrontesting/*")

#echo ${testdirs[@]}

#for D in services/core/*; do
#    if [ -d "${D}" ]; then
#        testdirs=("#testdirs[@]}" $D)
#    fi
#done
#echo "HIIIIIIIIIIIIIII"
#echo ${testdirs[@]}

filedirs="volttrontesting/platform"
testdirs="docs examples scripts volttron"
splitdirs="services/core"

echo "File tests"
for dir in $filedirs; do
  echo "File test for dir: $dir"
  for testfile in $dir/*.py; do
    echo "Using testfile: $testfile"
    pytest -v $testfile

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

   done
done

for dir in $testdirs; do
  pytest -v $testdirs

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

   done
done

for dir in $splitdirs; do

for D in "$dir/*"; do
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
done

exit $exit_code
