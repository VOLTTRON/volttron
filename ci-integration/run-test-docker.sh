#!/bin/bash
#Preliminary script to run pytests in separate docker containers

export FAST_FAIL=true

if [[ $# -eq 0 ]]; then
    NUM_PROCESSES=5
else
    NUM_PROCESSES=$1
fi

echo "RUNNING $NUM_PROCESSES PARALLEL PROCESSESS AT A TIME"

docker system prune --force

declare -a testqueue
declare -a runningprocs
declare -a outputfiles
declare -a containernames

#docker system prune --force

#docker build --network=host -t volttron_test_base -f ./ci-integration/virtualization/Dockerfile .
#docker build --network=host -t volttron_test_image -f ./ci-integration/virtualization/Dockerfile.testing .

#testdirs=(examples services volttron volttrontesting)
testdirs=(volttrontesting)
HAS_FAILED=0

push_test(){
    testpath="$1"
    testqueue+=($testpath)
}

pop_test(){
    next_test=${testqueue[0]}
    testqueue=("${testqueue[@]:1}")
}

run_test(){
#    bash /home/osboxes/repos/volttron-rabbitmq/ci-integration/sleep_ten.sh &
    local filename=$1;
    echo "Running test module $filename"
    base_filename=`basename $filename`
    docker run -e "IGNORE_ENV_CHECK=1" --name $base_filename \
        -t volttron_test_image pytest $filename > "$base_filename.result.txt" 2>&1 &
    runningprocs+=($!)
    sleep 1
    outputfiles+=("$base_filename.result.txt")
    containernames+=($base_filename)
}

exit_cleanly(){
    for container in containernames; do
        docker stop $container
        docker container rm $container
    done
    docker system prune --force
    exit 1
}

#LOOP through set of directories and run bunch of test files in parallel
for dir in ${testdirs[@]}
do
    for file in $( find $dir -type f -name "*test*.py"|grep -v "conftest.py")
    do
        echo $file;
        push_test $file;
    done
done

echo "There are ${#testqueue[@]} test modules to run";

while [[ ${#testqueue[@]} -gt 0 ]]; do
    # echo "looping procs runing are ${#runningprocs[@]}  num_procs is ${NUM_PROCESSES} testqueue is ${#testqueue[@]} "
    while [[ ${#runningprocs[@]} -lt ${NUM_PROCESSES} && ${#testqueue[@]} -gt 0 ]]; do
        # pop the front of the queue into the next_test variable
        pop_test
        run_test ${next_test}
    done

    i=0

    while [[ $i -lt ${#runningprocs[@]} ]]; do

        pid=${runningprocs[$i]}
        # Test whether or not the process id running the docker container
        # is still executing.  If it is not then we need to see what the
        # exit code was of the container.
        if [[ ! -e "/proc/${pid}" ]]; then
            exitcode=$(docker inspect ${containernames[$i]} --format='{{.State.ExitCode}}')

            if [[ ! $exitcode ]]; then
                HAS_FAILED=1
                if [[ ${FAST_FAIL} ]]; then
                    exit_cleanly
                fi
                echo "module ${containernames[$i]} FAILED"
            else
                rm ${outputfiles[$i]}
                echo "module ${containernames[$i]} PASSED"
            fi

            # Clean up the test container now that this process is done.
            docker container rm ${containernames[$i]}

            # Remove pid from the array of running procs.
            runningprocs=( ${runningprocs[@]:0:$i} ${runningprocs[@]:$((i + 1))} )
            outputfiles=( ${outputfiles[@]:0:$i} ${outputfiles[@]:$((i + 1))} )
            containernames=( ${containernames[@]:0:$i} ${containernames[@]:$((i + 1))} )
        fi
        i=$(( i+1 ))
        sleep 1
    done
done


while [[ ${#runningprocs[@]} -gt 0 ]]; do
    i=0

    while [[ $i -lt ${#runningprocs[@]} ]]; do

        pid=${runningprocs[$i]}
        # Test whether or not the process id running the docker container
        # is still executing.  If it is not then we need to see what the
        # exit code was of the container.
        if [[ ! -e "/proc/${pid}" ]]; then

            exitcode=$(docker inspect ${containernames[$i]} --format='{{.State.ExitCode}}')

            if [[ ! $exitcode ]]; then
                HAS_FAILED=1
                if [[ ${FAST_FAIL} ]]; then
                    exit_cleanly
                fi
                echo "module ${containernames[$i]} FAILED"
            else
                rm ${outputfiles[$i]}
                echo "module ${containernames[$i]} PASSED"
            fi

            # Clean up the test container now that this process is done.
            docker container rm ${containernames[$i]}

            # Remove pid from the array of running procs.
            runningprocs=( ${runningprocs[@]:0:$i} ${runningprocs[@]:$((i + 1))} )
            outputfiles=( ${outputfiles[@]:0:$i} ${outputfiles[@]:$((i + 1))} )
            containernames=( ${containernames[@]:0:$i} ${containernames[@]:$((i + 1))} )
            # echo "Process running ${#runningprocs[@]}"
        fi
        i=$(( i+1 ))
        sleep 0.5
    done
done

docker system prune --force

# if this is set to something besided 0 anywhere in the script then we have failed.
exit ${HAS_FAILED}
