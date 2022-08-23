import importlib
import pkgutil
import logging
import auth_protocol

_log = logging.getLogger(__name__)


# Simulates the installation of web service in to the environment.
# web_service = Path("../volttron-web-service").resolve()
# sys.path.insert(0, str(web_service))


def iter_namespace(ns_pkg):
    """
    Uses namespace package to locate all namespaces with the ns_pkg as its root.
    For example in our system any namespace package that starts with volttron.services
    should be detected.
    NOTE: NO __init__.py file should ever be located within any package volttron.services or
            the importing will break
    @param: ns_pkg: Namespace to search for modules in.
    """
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


"""
Map all of the discovered namespaces to the volttron.services import.  Build
a dictionary 'package' -> module.
"""
discovered_plugins = {
    name: importlib.import_module(name)
    for finder, name, ispkg in iter_namespace(auth_protocol)
}


"""
Manage the startup order of plugins available.  Note an error will
be raised and the server will not startup if the plugin doesn't exist.  
The plugins that are within this same codebase hold the "default" services
that should always be available in the system.  VOLTTRON requires that
the services be started in a specific order for its processing to work as
intended.
"""
plugin_startup_order = ["volttron.services.config_store", "volttron.services.auth"]

plugin_disabled = ["volttron.services.health"]

for p in plugin_startup_order:
    if p not in discovered_plugins:
        raise ValueError(f"Invalid plugin specified in plugin_startup_order {p}")
    _log.info(f"Starting plugin: {p}, {discovered_plugins[p]}")

for p, v in discovered_plugins.items():
    if p not in plugin_startup_order and p not in plugin_disabled:
        _log.info(f"Starting plugin {p}, {v}")