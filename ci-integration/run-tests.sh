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


#directories that need split into individual files
filedirs="volttrontesting/platform"
#directories that can be called as normal (recursive)
testdirs="docs examples scripts volttron volttrontesting/gevent volttrontesting/multiplatform volttrontesting/subsystems volttrontesting/testutils volttrontesting/zmq"
#directories that must have their subdirectories split
splitdirs="services/core/*"

echo "TestDirs"
for dir in $testdirs; do
  echo "*********TESTDIR: $dir"
  py.test -v $dir

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

echo "SplitDirs"
for dir in $splitdirs; do

for D in $dir; do
    if [ -d "${D}" ]; then
  echo "*********SPLITDIR: $D"
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

echo "File tests"
for dir in $filedirs; do
  echo "File test for dir: $dir"
  for testfile in $dir/*.py; do
    echo "Using testfile: $testfile"
    if [ $testfile != "volttrontesting/platform/packaging-tests.py" ]; then
       py.test -v $testfile

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
       else
         echo "Skipping $testfile"
     fi
   done
done

exit $exit_code
