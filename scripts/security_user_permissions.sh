#!/usr/bin/env bash

if [ -z "$UID" ] || [ $UID -ne 0 ]; then
  echo "Script should be run as root user or as sudo <path to this script>/secure_user_permission.sh"
  exit
fi

echo -n "Enter volttron platform user. User would be provided sudo access to volttron related commands:"
read volttron_user

echo "Creating volttron_agent user group"
echo "Adding Permissions to sudoers for VOLTTRON:"
# allow user to add and delete users using the volttron agent user pattern
while true; do
    valid=0
    echo -n "Enter Volttron instance name (volttron_<instance name>must be valid unix group):"
    read name
    if [[ $name =~ ^[a-z_]([a-z0-9_-]{1,23}|[a-z0-9_-]{1,23}\$)$ ]]
    # TODO check if that instance name is taken
    then
        if [ -f "/etc/sudoers.d/volttron" ]; then
            exists=`grep "volttron_$name" /etc/sudoers.d/volttron`
            if [ -z "$exists" ]; then
                valid=1
            else
                echo "Entries exists in /etc/sudoers.d/volttron for instance name $name"
                echo -n "Do you want to setup a different instance of volttron(Y/N)"
                read continue
                if [ $continue == "N" ] || [ $continue == "N" ]; then
                    exit
                fi
            fi
        else
            valid=1
        fi

        if [ $valid -eq 1 ]; then
            echo "Setting Volttron instance name to volttron_$name"
            break
        fi
    fi
done

echo "$volttron_user ALL= NOPASSWD: /usr/sbin/groupadd volttron_$name" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "$volttron_user ALL= NOPASSWD: /usr/sbin/usermod -a -G volttron_$name $USER" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "$volttron_user ALL= NOPASSWD: /usr/sbin/useradd volttron_* -r -G volttron_$name" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
# TODO want delete only users with pattern of particular group
echo "$volttron_user ALL= NOPASSWD: /usr/sbin/userdel volttron_*" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
# allow user to run all non-sudo commands for all volttron agent users
echo "$volttron_user ALL=(%volttron_$name) NOPASSWD: ALL" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "Permissions set for $volttron_user"
