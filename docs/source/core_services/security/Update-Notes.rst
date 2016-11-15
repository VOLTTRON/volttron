.. _Security-Update-Notes:
=====================
Security Update Notes
=====================

This is a list of updates to security-related functionality in VOLTTRON
that either break backward compatibility or may have noticeable impact
to the user.

Version 3.5rc1
==============

- ``$VOLTTRON_HOME/auth.json`` should not be edited with a text editor.
  Use ``volttron-ctl`` commands ``auth-list``, ``auth-add``, ``auth-remove``,
  and ``auth-update`` to view and manipulate that file.
- ``#``-style comments are no longer supported in ``$VOLTTRON_HOME/auth.json``.
  Use the ``comments`` and ``enabled`` fields.
  (See the :ref:`agent authentication walkthrough<AgentAuthentication>`.) 

Version 4.0
===========

- The ``$VOLTTRON_HOME/curve.key`` file has been replaced with a
  :ref:`key store`<Key-Stores>`. Use the ``scripts/update_curve_key.py``
  script to update an existing key pair.
- A ``mechanism`` field has been added to the auth file. Therefore,
  the ``credentials`` field no longer is prepended with a mechanism
  such as "CURVE:". VOLTTRON automatically updates the auth entires
  to use the new field.

  - Entries with a regular expression in the ``credentials`` field
    cannot be upgraded.

- Security-related commands for ``volttron-ctl`` have been moved to a
  ``auth`` subcommand.
  (See the :ref:`auth command documentation<AuthenticationCommands>`.)
