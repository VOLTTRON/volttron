#!/usr/bin/env bash

if [ -z "$UID" ] || [ $UID -ne 0 ]; then
  echo "Script should be run as root user or as sudo <path to this script>/secure_user_permission.sh"
  exit
fi

if [ -z ${USER} ]; then
 echo '$USER is not set. Finding user name for UID 0'
 USER=`awk -v val=0 -F ":" '$3==val{print $1}' /etc/passwd`
 echo "USER got based on uid 0 is $USER"
fi

echo "Creating volttron_agent user group"
echo "Adding Permissions to sudoers for VOLTTRON:"
# allow user to add and delete users using the volttron agent user pattern
while true; do
    echo -n "Enter Volttron instance name (volttron_<instance name>must be valid unix group):"
    read name
    if [[ $name =~ ^[a-z_]([a-z0-9_-]{1,23}|[a-z0-9_-]{1,23}\$)$ ]]
    # TODO check if that instance name is taken
    then
        echo "Setting Volttron instance name to volttron_$name"
        break
    fi
done

echo "$USER ALL= NOPASSWD: /usr/sbin/groupadd volttron_$name" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "$USER ALL= NOPASSWD: /usr/sbin/usermod -a -G volttron_$name $USER" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "$USER ALL= NOPASSWD: /usr/sbin/useradd volttron_* -r -G volttron_$name" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
# TODO want delete only users with pattern of particular group
echo "$USER ALL= NOPASSWD: /usr/sbin/userdel volttron_*" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
# allow user to run all non-sudo commands for all volttron agent users
echo "$USER ALL=(%volttron_$name) NOPASSWD: ALL" | sudo EDITOR='tee -a' visudo -f /etc/sudoers.d/volttron
echo "Permissions set for $USER"
