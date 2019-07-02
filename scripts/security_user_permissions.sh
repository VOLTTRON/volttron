#!/usr/bin/env bash
echo "Create volttron_agent user group"
echo "Adding Permissions to sudoers for VOLTTRON:"
# allow user to add and delete users using the volttron agent user pattern
echo "$USER ALL= NOPASSWD: /usr/sbin/groupadd volttron_agent" | sudo EDITOR='tee -a' visudo
groupadd volttron_agent
echo "$USER ALL= NOPASSWD: /usr/sbin/useradd volttron_* -G volttron_agent -d *" | sudo EDITOR='tee -a' visudo
echo "$USER ALL= NOPASSWD: /usr/sbin/userdel volttron_*" | sudo EDITOR='tee -a' visudo
# allow user to use su to run commands as the volttron agent user - this does
# not give volttron agent user sudoer permissions
echo "$USER ALL=(%volttron_agent) NOPASSWD: ALL" | sudo EDITOR='tee -a' visudo
echo "Permissions set for $USER"
