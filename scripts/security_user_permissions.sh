#!/usr/bin/env bash
echo "Create volttron_agent user group"
echo "Adding Permissions to sudoers for VOLTTRON:"
# allow user to add and delete users using the volttron agent user pattern
# TODO do we want the platform to recover the group
# TODO do we want the platform to recover users to the group
echo "$USER ALL= NOPASSWD: /usr/sbin/groupadd volttron_*" | sudo EDITOR='tee -a' visudo
# TODO group might want to be volttron_<instance_name>
# TODO username pattern might want to be volttron_<timestamp+millis>
echo "$USER ALL= NOPASSWD: /usr/sbin/useradd volttron_* -G volttron_agent -d *" | sudo EDITOR='tee -a' visudo
# TODO might want delete only users with pattern of particular group
# TODO appears to be problematic
echo "$USER ALL= NOPASSWD: /usr/sbin/userdel volttron_*" | sudo EDITOR='tee -a' visudo
# allow user to use su to run commands as the volttron agent user - this does
# not give volttron agent user sudoer permissions
echo "$USER ALL=(%volttron_agent) NOPASSWD: ALL" | sudo EDITOR='tee -a' visudo
echo "Permissions set for $USER"
