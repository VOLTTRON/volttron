#!/usr/bin/env bash

if [ -z "$UID" ] || [ $UID -ne 0 ]; then
  echo "Script should be run as root user or as sudo <path to this script>/secure_user_permission.sh"
  exit 1
fi

while true; do
    echo -n "Enter volttron platform user. User would be provided sudo access to specific commands:"
    read volttron_user
    id=`id -u $volttron_user`
    if [ ! -z "$id" ]; then
        if [ $id -ne 0 ]; then
            break
        else
            echo "Volttron platform cannot run as root user. Please provide a non root user"
        fi
    fi
done

# Set up volttron home config

default_home=`getent passwd "${volttron_user}"|cut -d\: -f 6`

while true; do
    echo -n "Absolute path to VOLTTRON_HOME directory [$default_home/.volttron]:"
    read volttron_home
    volttron_home="${volttron_home:-$default_home/.volttron}"
    if [[ "$volttron_home" = /* ]]; then
        break
    else
        echo "Please provide absolute path. $volttron_user should have write access to the directory"
    fi
done

if [ ! -d $volttron_home ]; then
    mkdir $volttron_home
    if [ $? -eq 0 ]; then
        chown $volttron_user $volttron_home
    else
        exit 1
    fi
else
    echo -n "
**WARNING** You are using a existing directory as volttron home."
    echo -n " You will NOT be able to revert to insecure mode once the changes \
are done. Changing the config file manually might result inconsistent \
volttron behavior. If you would like to continue please note the following,
       1. This script will manually restrict permissions for existing files and directory.
       2. Volttron process and all agents have to be restarted to take effect.
       3. If you have agents that connect to remote RMQ instances and then the \
***CSR approval process has to be repeated***
       4. Agents can only to write to its own agent-data dir. So if your agents \
writes to any directory outside vhome/agents/<agent-uuid>/<agent-name>/agent-name.agent-data \
move existing files and update configuration such that agent writes to agent-name.agent-data dir
"
    echo -n "Would you like to transition this existing VOLTTRON_HOME to secure mode (Y/N)"
    read continue
    if [ $continue == "Y" ] || [ $continue == "y" ]; then

        # if this is a existing volttron home directory, update file permissions of
        # existing files. Agent specific users will be granted access to its own
        # files at agent start

        # update access to others for the following files/directories
        # keystores and its subdirectory - remove RX for others.
        # known_hosts - should have read access
        # VOLTTRON_PID - remove read access to other
        # files in configuration_store - remove read access to others
        # files in packaged dir - remove files. Not used after agent install
        # move installed agent's keystore.json from agent-data dir to dist-info
        # agents dir -remove rwx from other for all dirs and files

        echo "Updating directory permissions...."
        files=(`find $volttron_home/keystores -type d`)
        for f in "${files[@]}";
        do
            echo $f
            chmod o-rwx $f
        done

        echo "Changing permissions for agents/* dir"
        files=(`find $volttron_home/agents/* -type d`)
        for f in "${files[@]}";
        do
            chmod o-rwx $f
        done

        echo "Updating file permissions....."

        if [ -f $volttron_home/known_hosts ]; then
            echo $volttron_home/known_hosts
            chmod a+r $volttron_home/known_hosts
        fi
        if [ -f $volttron_home/VOLTTRON_PID ]; then
            echo $volttron_home/VOLTTRON_PID
            chmod o-rwx $volttron_home/VOLTTRON_PID
        fi
        for f in $volttron_home/configuration_store/*.store;
        do
            if [ -f $f ]; then
                echo $f
                chmod o-rwx  $f
            fi
        done
        if [ -d $volttron_home/packaged ]; then
            files=(`find $volttron_home/packaged -type f`)
            for f in "${files[@]}";
            do
                if [ -f $f ]; then
                    echo $f
                    rm $f
                fi
            done
        fi

        echo "Changing file permissions for agents dir"
        files=(`find $volttron_home/agents -type f`)
        for f in "${files[@]}";
        do
            chmod o-rwx $f
        done

        files=(`find $volttron_home/agents -type f -name keystore.json`)
        for f in "${files[@]}";
        do
            echo $f
            d=$(dirname "$f")
            if [[ "$d" == *agent-data ]]
            then
                # move to dist-info dir
                agent_dir=$(dirname "$d")
                agent_name=$(basename "$agent_dir")
                new_dir=$agent_dir/$agent_name.dist-info
                echo "moving keystore.json from $d to $new_dir"
                mv $f $new_dir/keystore.json
            fi
        done

    else
        exit 0
    fi
fi

if [ -f $volttron_home/config ]; then
    line=`grep secure-agent-users $volttron_home/config`
    if [ -z "$line" ]; then
        # append to end of file
        echo "entry for secure-agent-users does not exists. appending to end of file"
        echo "secure-agent-users = True" >> $volttron_home/config
    else
        # replace false to true
        sed -i 's/secure-agent-users = False/secure-agent-users = True/' $volttron_home/config
    fi
    # grab instance name from config and trim leading and trailing white spaces
    name=`grep instance-name $volttron_home/config | cut -d "=" -f 2 | sed 's/^[ \t]*//;s/[ \t]*$//'`
else
    echo "[volttron]" > $volttron_home/config
    echo "secure-agent-users = True" >> $volttron_home/config
    chown $volttron_user $volttron_home/config
fi

script=${BASH_SOURCE[0]}
script=`realpath $script`
source_dir=$(dirname "$(dirname "$script")")


echo "Creating volttron_agent user group"
echo "Adding Permissions to sudoers for user: $volttron_user"
# allow user to add and delete users using the volttron agent user pattern
while true; do
    name_from_config=""
    valid=0
    if [ -z "$name" ]; then
        echo -n "Enter Volttron instance name (volttron_<instance name>must be valid unix group):"
        read name
    else
        echo "Instance name from $volttron_home/config is $name"
        name_from_config=1
    fi

    if [[ $name =~ ^[a-z_]([a-z0-9_-]{1,23}|[a-z0-9_-]{1,23}\$)$ ]]
    then
        if [ -f "/etc/sudoers.d/volttron" ]; then
            exists=`grep "volttron_$name" /etc/sudoers.d/volttron`
            if [ -z "$exists" ]; then
                valid=1
            else
                echo "Entries exists in /etc/sudoers.d/volttron for instance name $name"
                if [ -z "$name_from_config" ]; then
                    # If name is not from config as user option to pick different instance_name
                    echo -n "Do you want to setup a different instance of volttron(Y/N)"
                    read continue
                    if [ $continue == "N" ] || [ $continue == "n" ]; then
                        # write instance-name to config file
                        echo "instance-name = $name" >> $volttron_home/config
                        echo "Volttron secure mode setup is complete"
                        exit 0
                    else
                        name=""
                    fi
                else
                    echo "Volttron secure mode setup is complete"
                    exit 0
                fi
            fi
        else
            valid=1
        fi

        if [ $valid -eq 1 ]; then
            echo "Setting Volttron instance name to $name"
            if [ -z "$name_from_config" ]; then
                # write instance-name to config file
                echo "instance-name = $name" >> $volttron_home/config
            fi
            break
        fi
    fi
done

echo "$volttron_user ALL= NOPASSWD: /usr/sbin/groupadd volttron_$name" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "$volttron_user ALL= NOPASSWD: /usr/sbin/usermod -a -G volttron_$name $USER" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "$volttron_user ALL= NOPASSWD: /usr/sbin/useradd volttron_[1-9]* -r -G volttron_$name" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "$volttron_user ALL= NOPASSWD: $source_dir/scripts/secure_stop_agent.sh volttron_[1-9]* [1-9]*" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron

# TODO want delete only users with pattern of particular group
echo "$volttron_user ALL= NOPASSWD: /usr/sbin/userdel volttron_[1-9]*" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
# allow user to run all non-sudo commands for all volttron agent users
echo "$volttron_user ALL=(%volttron_$name) NOPASSWD: ALL" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "Permissions set for $volttron_user"
echo "Volttron secure mode setup is complete"