#!/bin/bash
#Preliminary script to run pytests in separate docker containers

docker build --network=host -t volttron_test_base -f ./ci-integration/virtualization/Dockerfile .
docker build --network=host -t volttron_test_image -f ./ci-integration/virtualization/Dockerfile.testing .

#testdirs="examples services volttron volttrontesting"
testdirs="services/core/ActuatorAgent"

for dir in ${testdirs[@]}
do
    files=`find $dir -type f -name "*.py"`
    #echo $files
    for filename in ${files[@]}
    do
        #echo $filename
        base_filename=`basename $filename`
        if [[ $base_filename == *"test"* ]]; then
            echo $filename
            docker run -e "IGNORE_ENV_CHECK=1" -it volttron_test_image pytest $filename &> "$base_filename.result.txt" &
        fi
    done
done
