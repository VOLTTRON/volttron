# -*- coding: utf-8 -*-
"""
Regression test for #3235: the historian, tagging, and dbdriver test
modules must read MySQL, PostgreSQL, and MongoDB ports from
MYSQL_PORT, POSTGRES_PORT, and MONGODB_PORT, and fall back to the
hardcoded default when a variable is unset. Importing these modules
needs no platform, database, or docker container.
"""
import importlib

import pytest

import volttrontesting.services.aggregate_historian.test_aggregate_historian as test_aggregate_historian
import volttrontesting.services.historian.test_dbdriver as test_dbdriver
import volttrontesting.services.historian.test_historian as test_historian
import volttrontesting.services.tagging.test_tagging as test_tagging

# Reloaded together so a variable set before one module's first import in
# this process (or left by an earlier test) cannot make its port dict
# stale relative to the others.
_MODULES = (
    test_aggregate_historian,
    test_dbdriver,
    test_historian,
    test_tagging,
)


def _reload_modules():
    for module in _MODULES:
        importlib.reload(module)


def _mysql_ports():
    return {
        "test_aggregate_historian.mysql_aggregator":
            test_aggregate_historian.mysql_aggregator["connection"]["params"]["port"],
        "test_aggregate_historian.mysql_aggregator_with_table_names":
            test_aggregate_historian.mysql_aggregator_with_table_names["connection"]["params"]["port"],
        "test_historian.mysql_platform":
            test_historian.mysql_platform["connection"]["params"]["port"],
        "test_tagging.mysql_historian":
            test_tagging.mysql_historian["connection"]["params"]["port"],
    }


def _postgres_ports():
    return {
        "test_aggregate_historian.postgresql_aggregator":
            test_aggregate_historian.postgresql_aggregator["connection"]["params"]["port"],
        "test_aggregate_historian.postgresql_aggregator_with_table_names":
            test_aggregate_historian.postgresql_aggregator_with_table_names["connection"]["params"]["port"],
        "test_historian.postgresql_platform":
            test_historian.postgresql_platform["connection"]["params"]["port"],
        "test_dbdriver.postgres_connection_params":
            test_dbdriver.postgres_connection_params["port"],
    }


def _mongodb_ports():
    return {
        "test_aggregate_historian.mongo_aggregator":
            test_aggregate_historian.mongo_aggregator["connection"]["params"]["port"],
        "test_historian.mongo_platform":
            test_historian.mongo_platform["connection"]["params"]["port"],
        "test_tagging.mongodb_config":
            test_tagging.mongodb_config["connection"]["params"]["port"],
    }


# (env var, hardcoded default, a non-default override, the site accessor)
PORT_CASES = (
    ("MYSQL_PORT", 3306, 23306, _mysql_ports),
    ("POSTGRES_PORT", 5432, 25432, _postgres_ports),
    ("MONGODB_PORT", 27017, 47017, _mongodb_ports),
)


@pytest.mark.parametrize("var, default, override, ports", PORT_CASES, ids=[case[0] for case in PORT_CASES])
def test_default_port_with_variable_unset(monkeypatch, var, default, override, ports):
    monkeypatch.delenv(var, raising=False)
    _reload_modules()
    try:
        for site, value in ports().items():
            assert value == default, f"{site} port should default to {default} with {var} unset, got {value}"
    finally:
        _reload_modules()


@pytest.mark.parametrize("var, default, override, ports", PORT_CASES, ids=[case[0] for case in PORT_CASES])
def test_port_override_from_environment(monkeypatch, var, default, override, ports):
    monkeypatch.setenv(var, str(override))
    _reload_modules()
    try:
        for site, value in ports().items():
            assert isinstance(value, int), f"{site} port must be an int, got {type(value)}"
            assert value == override, f"{site} port should pick up {var}={override}, got {value}"
    finally:
        # Restore the variable before reloading so a later test in this
        # session that imports these modules sees the hardcoded default.
        monkeypatch.delenv(var, raising=False)
        _reload_modules()
