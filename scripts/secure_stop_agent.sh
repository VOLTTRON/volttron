#!/usr/bin/env bash

# Function to stop a process using the given kill signal and wait at most for the given number of seconds
stop_process_and_wait(){
    local pid=$1
    local signal=$2
    local count
    ((count=$3*2))
    local timeout=0
    kill -s $signal $pid
    exit_code="$?"
    if [ $exit_code -ne 0 ]; then
       echo "Agent stop failed"
       return 1
    fi
    # wait for agent to stop
    i=0
    while kill -0 "$pid" ; do
        sleep 0.5
        let "i++"
        if [ $i -eq $count ]; then
            timeout=1
            break
        fi
    done
    return $timeout
}

user=$1
pid=$2

#  Verify script is run as root or using sudo because agents will be running as root in secure mode
if [ -z "$UID" ] || [ $UID -ne 0 ]; then
  echo "Script should be run as root user or as sudo <path to this script>/secure_stop_agent.sh"
  exit
fi

# user running the agent should be of the format volttron_[0-9]+
# Agent users created by platform have prefix volttron_<timestamp>
re='volttron_[0-9]+'
if ! [[ $user =~ $re ]]; then
    echo "Invalid user $user"
    echo "Usage: <path>/secure_stop_agent.sh <user name of requester> <pid of agent to be stopped>"
    exit 1
fi

# Check if pid is passed and it is a number
re='^[0-9]+$'
if [ -z "$pid" ] || ! [[ $pid =~ $re ]]; then
    echo "Invalid process id..."
    echo "Usage: <path>/secure_stop_agent.sh <user name of requester> <pid of agent to be stopped>"
    exit 2
fi

# Attempt to find process corresponding to pid
command=`ps -h -p $pid -o command`
exit_code="$?"

# If exit code is not 0 for the ps command then no such pid exists
if [ $exit_code -ne 0 ]; then
    echo "Invalid process id $pid. Process id does not correspond to any valid agent process"
    echo "Usage: <path>/secure_stop_agent.sh <user name of requester> <pid of agent to be stopped>"
    exit 3
fi

# if we find a command check the pattern
# command should be of the pattern
# sudo -E -u <username passed to this script> /<some path to volttron source>/env/bin/python -m <agent name>

re="^sudo -E -u $user /.+/env/bin/python -m .+"
if [[ ! $command =~ $re ]]; then
    echo "Invalid process id. pid does not correspond to a volttron agent owned by user $user"
    echo "Usage: <path>/secure_stop_agent.sh <user name of requester> <pid of agent to be stopped>"
    exit 4
fi

agent_pid=`pgrep -P $pid `
exit_code="$?"

# If exit code is not 0 for the ps command then no such pid exists
if [ $exit_code -ne 0 ]; then
    echo "Invalid process id $pid. Process id does not have valid child process"
    echo "Usage: <path>/secure_stop_agent.sh <user name of requester> <pid of agent to be stopped>"
    exit 5
fi

echo "Sending SIGINT signal to $agent_pid  "
# Attempt 1 send SIGINT give process to complete onstop functions
stop_process_and_wait $agent_pid SIGINT 60
if [ $? -eq 0 ]; then
    echo  "Agent stopped"
    exit 0
fi

echo "Sending SIGTERM signal to $agent_pid  "

# Attempt 2 send terminate
stop_process_and_wait $agent_pid SIGTERM 30
if [ $? -eq 0 ]; then
    echo  "Agent terminated"
    exit 0
fi

echo "Sending SIGKILL signal to $agent_pid  "

# Attempt 3 kill
stop_process_and_wait $agent_pid SIGKILL 30
if [ $? -eq 0 ]; then
    echo  "Agent killed"
    exit 0
else
    echo "Unable to stop/kill agent  "
    exit 5
fi
