.. _Agent_Watcher

=============
Agent Watcher
=============

The Agent Watcher is used to monitor agents running on a VOLTTRON instance.
Specifically it monitors whether a set of VIP identities (peers) are connected
to the instance.  If any of the peers in the set are not present then an alert
will be sent.