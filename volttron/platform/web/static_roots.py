"""Which directories platform_web serves files from, and which files in them.

An agent may register a static root inside its own install directory or
inside a configured ``web-static-roots`` entry. Agent package metadata
(``*.dist-info``, which holds the agent's ``keystore.json``) and agent data
(``*.agent-data``) are never served from any root.
"""
import logging
import os
import stat

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


def configured_roots(entries, home, protected_files=()):
    """Return the resolved ``web-static-roots`` entries that pass the root
    rules and hold none of protected_files; log each entry that does not at
    ERROR and drop it."""
    home = os.path.realpath(home)
    protected = [os.path.realpath(path) for path in protected_files if path]
    kept = []
    for entry in entries or ():
        if '\x00' in entry:
            reason = 'not a valid path'
        elif not os.path.isabs(entry):
            reason = 'not an absolute path'
        else:
            root = os.path.realpath(entry)
            if not os.path.isdir(root):
                reason = 'not a directory'
            elif _within(root, home):
                reason = 'inside VOLTTRON_HOME'
            elif any(_within(path, root) for path in protected):
                reason = 'holds the web server key or certificate'
            else:
                reason = _general_refusal(root, home)
        if reason:
            _log.error('web-static-roots entry %r dropped: %s', entry, reason)
        else:
            kept.append(root)
    return tuple(kept)


def _installed_identity(install):
    """The whole IDENTITY file of an install directory, or None when it has
    no IDENTITY file that is a readable regular file."""
    path = os.path.join(install, 'IDENTITY')
    try:
        # Checked on the opened file, so nothing can be swapped in between;
        # non-blocking, so opening a FIFO cannot stall the platform process.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as err:
        _log.warning('agent install %r skipped: IDENTITY unreadable: %s', install, err)
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError('not a regular file')
        with os.fdopen(os.dup(fd), 'rb') as file:
            # Compared whole, as the platform reads it when starting the agent.
            return file.read().decode('utf-8')
    except (OSError, ValueError) as err:
        _log.warning('agent install %r skipped: IDENTITY unreadable: %s', install, err)
        return None
    finally:
        os.close(fd)


def install_dirs(home, identity):
    """Install directories under <home>/agents whose IDENTITY file names
    identity, or None when <home>/agents cannot be listed. A symlinked
    install directory is never the caller's."""
    agents = os.path.join(os.path.realpath(home), 'agents')
    try:
        uuids = os.listdir(agents)
    except FileNotFoundError:
        return []
    except OSError as err:
        _log.warning('agent install directories %r cannot be read: %s', agents, err)
        return None
    found = []
    for uuid in uuids:
        install = os.path.join(agents, uuid)
        if os.path.islink(install):
            continue
        if _installed_identity(install) == identity:
            found.append(install)
    return found


def root_refusal(root, identity, home, configured):
    """Why identity may not register the resolved directory root, or None."""
    home = os.path.realpath(home)
    reason = _general_refusal(root, home)
    if reason:
        return reason
    if _within(root, home):
        installs = install_dirs(home, identity)
        if installs is None:
            return 'the agent install directories cannot be read'
        for install in installs:
            if _within(root, install):
                # <uuid>/ and <uuid>/<package>/ hold the package metadata and data.
                if len(os.path.relpath(root, install).split(os.sep)) < 2:
                    return 'the root contains agent package metadata or agent data'
                return None
        return 'the root is inside VOLTTRON_HOME outside the agent install directory'
    if any(_within(root, allowed) for allowed in configured):
        return None
    return 'the root is not in the agent install directory or a web-static-roots entry'


def file_to_serve(root, path_info):
    """The file a request names under the resolved root, or None when it
    must not be served. The root is never re-resolved, so replacing it with
    a symlink after registration does not move it."""
    if _has_private_part(path_info, '/'):
        return None
    resolved = os.path.realpath(root + path_info)
    if not _within(resolved, root):
        return None
    if _has_private_part(os.path.relpath(resolved, root)):
        return None
    return resolved


def open_checked(path):
    """Open path, a file_to_serve result, for reading; return None when the
    opened file is no longer the regular file at that resolved path, as when
    a component was swapped for a symlink after the check."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        opened = os.fstat(fd)
        current = os.stat(path)
        if (stat.S_ISREG(opened.st_mode) and os.path.realpath(path) == path
                and (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino)):
            return os.fdopen(os.dup(fd), 'rb')
    except OSError:
        pass
    finally:
        os.close(fd)
    return None
