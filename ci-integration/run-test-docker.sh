#!/usr/bin/env bash


NUM_PROCESSES=1

#do_something_with_line()
#{
#    line=$1
#    #echo "running $line"
#    docker run -t volttron-test-image pytest -k $line &> "$line.result.txt" &  # ls -la # env/bin/pytest -k $line" &> "$line.results.txt"
#    #docker run -t volttron-test-image "env/bin/pytest -k $line" &> "$line.results.txt"
#    #docker run -d -t volttron-test-image pytest -k $linepwd &>$line.results.txt # "/bin/bash && echo \$PATH"
#    #docker run -t volttron-test-image "which pytest"
#
#}

docker build --network=host -t volttron-test-image -f ./virtualization/Dockerfile.testing ../

area2=( test_pubsub_authorized test_pubsub_unauthorized test_agent_)
count=0
for line in ${area2[@]}
do
#    while [ `jobs | wc -l` -gt $NUM_PROCESSES ]
#    do
#        echo "Number of jobs: " `jobs | wc -l`
#        sleep 5
#    done

    docker run -t volttron-test-image pytest -k $line &> "$line.result.txt" &
    echo $!
    if [ $count == 0 ] ; then
        export PID=$!
        echo $PID
        count=1
    else
        wait $PID
        count=0
    fi
done

wait
#echo "Now here!"
#
#while [ `jobs | wc -l` -gt 0 ]
#do
#    echo `jobs`
#    sleep 5
#done
