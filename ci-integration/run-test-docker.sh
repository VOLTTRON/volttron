#!/bin/bash
# set -x # log all shell commands for debugging.
set -e # fail if any command errors without being caught with an || or an 'if'.

# The following script builds a volttron test image and then
# runs each of the test modules inside a docker container based
# upon the test image.

# Default to fast fail though allow it to be overwritten.
#export FAST_FAIL=${FAST_FAIL:-true}

# A possible argument passed to the script is the number docker containers
# to run at a single time.
if [[ $# -eq 0 ]]; then
    export NUM_PROCESSES=${NUM_PROCESSES:-3}
else
    export NUM_PROCESSES=$1
fi

export FAST_FAIL=${FAST_FAIL:-true}

pip list
echo "RUNNING $NUM_PROCESSES PARALLEL PROCESSESS AT A TIME"
echo "FAST_FAIL IS $FAST_FAIL"

# Before actually running odcker containers prune all dangling images
# and stopped containers.
docker system prune --force

# Declare variables to maintain the state of the running
# docker images.
declare -a testqueue        # Holds all of the queued test modules
declare -a runningprocs     # Holds the currently running docker processes
declare -a outputfiles      # Holds the output files from the logs of the docker processes
declare -a containernames   # Holds the name of the containers that have been started

docker build --network=host -t volttron_test_base -f ./ci-integration/virtualization/Dockerfile .
docker build --network=host -t volttron_test_image -f ./ci-integration/virtualization/Dockerfile.testing .

# Specific directories to scan for tests in
testdirs=(services volttrontesting)
ignoredirs=(services/core/DNP3Agent services/core/IEEE2030_5Agent services/core/OpenADRVenAgent)

# State variable for when a test has failed the entire set needs to be considered
# failed.
HAS_FAILED=0

set +e # allow this script to handle errors.

# method to push a test module into the queue
push_test(){
    testpath="$1"
    testqueue+=("$testpath")
}

# method to get a test module out of the queue
# the variable next_test is available after this function to be used
# with the popped value.
pop_test(){
    next_test=${testqueue[0]}
    testqueue=("${testqueue[@]:1}")
}

# Starts a single test module running.  This updates all of the
# global state arrays.
run_test(){
#    bash /home/osboxes/repos/volttron-rabbitmq/ci-integration/sleep_ten.sh &
    local filename="$1"
    echo "Running test module $filename"
    base_filename="$(basename "$filename")"
    # Start the docker run module.
    docker run -e "IGNORE_ENV_CHECK=1" -e "CI=$CI" --name "$base_filename" \
            -t --network="host" -v /var/run/docker.sock:/var/run/docker.sock volttron_test_image \
            pytest "$filename" > "$base_filename.result.txt" 2>&1 &

    runningprocs+=($!)
    outputfiles+=("$base_filename.result.txt")
    containernames+=("$base_filename")
    sleep 0.5
}


# This method is used to clean up containers when FAST_FAIL is set to true
# and failed tests are found.
exit_cleanly(){
    echo "Cleaning up test containers before exiting!"
    for container in "${containernames[@]}"; do
        docker stop "$container"
        docker container rm "$container"
    done
    docker system prune --force
    exit 1
}

# Process one of the docker pid files.
process_pid(){
    local index=$1
    local pid=${runningprocs[$index]}

    # Test whether or not the process id running the docker container
    # is still executing.  If it is not then we need to see what the
    # exit code was of the container.
    if [[ ! -e "/proc/${pid}" ]]; then
        exitcode=$(docker inspect "${containernames[$index]}" --format='{{.State.ExitCode}}')

        #echo "Exit code is ${exitcode}"
        # Exit code 5 is if there are no tests within the file so we filter that out
        if [[ $exitcode -ne 0  ]]; then
            if [[ $exitcode -eq 5 ]]; then
                echo "module ${containernames[$index]} NO TESTS RAN"
            else
                echo "module ${containernames[$index]} FAILED"
                HAS_FAILED=1
                #echo "FAST_FAIL is ${FAST_FAIL} if its 0 should start clean exit procedure."
                if [[ ${FAST_FAIL} -eq 0 && -n ${CI} ]]; then
                    docker logs "${containernames[$index]}"
                fi
                if [ ${FAST_FAIL} ]; then
                    echo "Exiting cleanly now!"
                    exit_cleanly
                else
                    echo "Test failed. Keep running rest of tests."
                fi
            fi
        else
            # process passed so cleanup the result file.
            echo "module ${containernames[$index]} PASSED removing: ${outputfiles[$index]}"
            rm "${outputfiles[$index]}"
        fi

        # Clean up the test container now that this process is done.
        docker container rm "${containernames[$index]}" &>/dev/null

        # Remove pid from the array of running procs.
        runningprocs=( "${runningprocs[@]:0:$index}" "${runningprocs[@]:$((index + 1))}" )
        outputfiles=( "${outputfiles[@]:0:$index}" "${outputfiles[@]:$((index + 1))}" )
        containernames=( "${containernames[@]:0:$index}" "${containernames[@]:$((index + 1))}" )
    fi
    i=$(( i+1 ))
}

#LOOP through set of directories and run bunch of test files in parallel
for dir in "${testdirs[@]}"
do
    for file in $( find $dir -type f -name "test*.py" -o -name "*test.py" ! -name "*conftest.py" )
    do
        echo "$file";
        ignore=0
        for pattern in "${ignoredirs[@]}"; do
            if [[ $file == *"$pattern"* ]]; then
                echo "$file IGNORED"
                ignore=1
                break
            fi
        done
        if [[ $ignore == 0 ]]; then
            push_test "$file";
        fi
    done
done

echo "There are ${#testqueue[@]} test modules to run";

# Loop through the queue until there isn't any left
while [[ ${#testqueue[@]} -gt 0 ]]; do

    # Start the number of processes requested
    while [[ ${#runningprocs[@]} -lt ${NUM_PROCESSES} && ${#testqueue[@]} -gt 0 ]]; do
        # pop the front of the queue into the next_test variable
        pop_test
        run_test "${next_test}"
    done

    i=0
    # Loop through processes that are running.  Check each process in the
    # array and process the return code for each process that is not running
    # any longer.
    while [[ $i -lt ${#runningprocs[@]} ]]; do
        process_pid $i
    done
    # echo "Running ${#runningprocs[@]} processes: ${runningprocs[@]}"
    sleep 10
done

# Final loop to finish the running processes before exiting the script.
while [[ ${#runningprocs[@]} -gt 0 ]]; do
    i=0

    # Loop through processes that are running.  Check each process in the
    # array and process the return code for each process that is not running
    # any longer.
    while [[ $i -lt ${#runningprocs[@]} ]]; do
        process_pid $i
    done
    #echo "Running ${#runningprocs[@]} processes: ${runningprocs[@]}"
    sleep 10
done

docker system prune --force

# if this is set to something besided 0 anywhere in the script then we have failed.
exit ${HAS_FAILED}
