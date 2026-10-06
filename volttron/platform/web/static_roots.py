"""Which directories platform_web serves files from, and which files in them.

An agent may register a static root inside its own install directory or
inside a configured ``web-static-roots`` entry. Agent package metadata
(``*.dist-info``, which holds the agent's ``keystore.json``) and agent data
(``*.agent-data``) are never served from any root.
"""
import logging
import os

_log = logging.getLogger(__name__)

_PRIVATE_SUFFIXES = ('.dist-info', '.agent-data')
_PRIVATE_NAMES = frozenset({'keystore.json'})


def is_private_name(name):
    folded = name.casefold()
    return folded.endswith(_PRIVATE_SUFFIXES) or folded in _PRIVATE_NAMES


def _has_private_part(path, sep=os.sep):
    return any(is_private_name(part) for part in path.split(sep) if part)


def _within(path, parent):
    return os.path.commonpath([path, parent]) == parent


def _general_refusal(root, home):
    """Why a resolved root may not be served from any source, or None."""
    if _has_private_part(root):
        return 'the root is or is inside agent package metadata or agent data'
    if _within(home, root):
        return 'the root contains VOLTTRON_HOME'
    return None


def configured_roots(entries, home):
    """Return the resolved ``web-static-roots`` entries that pass the root
    rules; log each entry that does not at ERROR and drop it."""
    home = os.path.realpath(home)
    kept = []
    for entry in entries or ():
        if not os.path.isabs(entry):
            reason = 'not an absolute path'
        else:
            root = os.path.realpath(entry)
            if not os.path.isdir(root):
                reason = 'not a directory'
            elif _within(root, home):
                reason = 'inside VOLTTRON_HOME'
            else:
                reason = _general_refusal(root, home)
        if reason:
            _log.error('web-static-roots entry %r dropped: %s', entry, reason)
        else:
            kept.append(root)
    return tuple(kept)


def install_dirs(home, identity):
    """Resolved install directories under <home>/agents whose IDENTITY file
    names identity. A symlinked install directory is never the caller's."""
    agents = os.path.join(os.path.realpath(home), 'agents')
    try:
        uuids = os.listdir(agents)
    except FileNotFoundError:
        return []
    found = []
    for uuid in uuids:
        install = os.path.join(agents, uuid)
        if os.path.islink(install):
            continue
        try:
            with open(os.path.join(install, 'IDENTITY'), 'rt') as file:
                # Read as the platform reads it (aip.agent_identity).
                installed = file.readline(64)
        except OSError:
            # Not an installed agent's directory, or not one this platform can
            # read; either way it is not the caller's.
            continue
        if installed == identity:
            found.append(install)
    return found


def root_refusal(root, identity, home, configured):
    """Why identity may not register the resolved directory root, or None."""
    home = os.path.realpath(home)
    reason = _general_refusal(root, home)
    if reason:
        return reason
    for install in install_dirs(home, identity):
        if _within(root, install):
            # <uuid>/ and <uuid>/<package>/ hold the package metadata and data.
            if len(os.path.relpath(root, install).split(os.sep)) < 2:
                return 'the root contains agent package metadata or agent data'
            return None
    if _within(root, home):
        return 'the root is inside VOLTTRON_HOME outside the agent install directory'
    if any(_within(root, allowed) for allowed in configured):
        return None
    return 'the root is not in the agent install directory or a web-static-roots entry'

