#!/bin/bash
#Preliminary script to run pytests in separate docker containers

export FAST_FAIL=0

if [[ $# -eq 0 ]]; then
    NUM_PROCESSES=3
else
    NUM_PROCESSES=$1
fi

echo "RUNNING $NUM_PROCESSES PARALLEL PROCESSESS AT A TIME"

docker build --network=host -t volttron_test_base -f ./ci-integration/virtualization/Dockerfile .
docker build --network=host -t volttron_test_image -f ./ci-integration/virtualization/Dockerfile.testing .

testdirs=(examples services volttron volttrontesting)
HAS_FAILED=0

#Funtion to pytests per file in separate docker containers
run_tests() {
    local files=("$@")
    local len=${#files[@]}
    local container_names=()
    local i=0
    local pids=""
    local full_filenames=()
    pwd
    for filename in ${files[@]}
    do
        base_filename=`basename $filename`
        docker run -e "IGNORE_ENV_CHECK=1" --name $base_filename \
            -t volttron_test_image pytest $filename > "$base_filename.result.txt" 2>&1 &
        sleep 1
        pids[$i]=$!
        container_names[$i]=$base_filename
        output_files[$i]="$base_filename.result.txt"
        let i++
    done

    echo "INPUT PROCESS IDs: ${pids[@]}"
    echo "INPUT CONTAINER NAMESs: ${container_names[@]}"
    echo "INPUT FILES: ${files[@]}"

    for ((x=0; x< $len; x++)); do
        echo "WAITING ON" ${container_names[$x]}
        wait ${pids[$x]}

        if [[ $? -eq 0 ]]; then
            echo "Job" ${files[$x]} "all tests: PASSED"
        else
            if [[ $? -ne 5 ]]; then
                echo $?
                echo "Job" ${files[$x]} "some tests: FAILED"
                docker logs ${container_names[$x]}
                HAS_FAILED=1
                if [[ ${FAST_FAIL} ]]; then
                    echo "Fast failing!"
                    docker rm ${container_names[$x]}
                    exit $HAS_FAILED
                fi
            fi
        fi
        docker rm ${container_names[$x]}
        rm ${output_files[$x]}
    done
}

#LOOP through set of directories and run bunch of test files in parallel
for dir in ${testdirs[@]}
do
    test_files=(`find $dir -type f -name "*test*.py"|grep -v "conftest.py"`)
    echo ${test_files[@]}
    max_files=${#test_files[@]}
    echo ${max_files}

    count=$(( max_files/NUM_PROCESSES ))
    rem=$(( max_files%NUM_PROCESSES ))
    echo $count $rem
    c=0
    files_subset=()

    for ((c=0; c<$count; c++))
    do
        offset=$(( c*NUM_PROCESSES ))
        files_subset=("${test_files[@]:$offset:$NUM_PROCESSES}")
        run_tests ${files_subset[@]}
    done
    if [[ $rem -gt 0 ]]; then
        offset=$(( c*NUM_PROCESSES ))
        files_subset=(${test_files[@]:$offset:$rem})
        run_tests ${files_subset[@]}
    fi
done

# if this is set to something besided 0 anywhere in the script then we have failed.
exit $HAS_FAILED