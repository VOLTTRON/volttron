#!/usr/bin/env bash
# DO NOT RUN THIS SCRIPT AS ROOT - IT WILL NOT WORK
# Run the script normally, it will ask you for your password for commands that require root
echo "Create volttron_agent user group"
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
echo "$USER ALL= NOPASSWD: /usr/sbin/groupadd volttron_$name" | sudo EDITOR='tee -a' visudo
echo "$USER ALL= NOPASSWD: /usr/sbin/useradd volttron_* -G volttron_$name -d *" | sudo EDITOR='tee -a' visudo
# TODO might want delete only users with pattern of particular group
echo "$USER ALL= NOPASSWD: /usr/sbin/userdel volttron_*" | sudo EDITOR='tee -a' visudo
# allow user to use su to run commands as the volttron agent user - this does
# not give volttron agent user sudoer permissions
echo "$USER ALL=(%volttron_agent) NOPASSWD: ALL" | sudo EDITOR='tee -a' visudo
echo "Permissions set for $USER"
