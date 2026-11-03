# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

"""
Fast, no-platform unit tests for WeatherCache's cache-size management: the
page-count arithmetic, the trim loop's termination when nothing more can be
deleted, and the effect of a successful trim.

These drive the real sqlite3-backed WeatherCache against a real database
file (no mocked cursor), and never start an agent or a platform.
"""

import logging
import sqlite3

import pytest

from volttron.platform.agent.base_weather import WeatherCache

pytestmark = pytest.mark.weather


def _pragma_used_pages(conn):
    """Independently derive the used-page figure from raw PRAGMAs, so the
    test does not simply re-execute the code path it is checking."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]
    cursor.execute("PRAGMA freelist_count")
    freelist_count = cursor.fetchone()[0]
    return page_count, freelist_count


def _make_cache(tmp_path, api_services, name="weather.sqlite"):
    # max_size_gb=None skips the constructor's own manage_cache_size() call,
    # so each test controls exactly when trimming runs.
    return WeatherCache(
        database_file=str(tmp_path / name),
        api_services=api_services,
        max_size_gb=None,
    )


HIST_SERVICES = {
    "hist_table": {"type": "history", "update_interval": None, "description": None},
}


@pytest.fixture
def hist_cache(tmp_path):
    """A WeatherCache with one empty history table and no size limit."""
    cache = _make_cache(tmp_path, HIST_SERVICES)
    yield cache
    if cache._sqlite_conn is not None:    # a test may have closed it already
        cache.close()


def _fill_hist_table(conn, rows=250, payload_size=500):
    """Insert rows of padded records into hist_table so the file spans many pages."""
    payload = "x" * payload_size
    conn.cursor().executemany(
        "INSERT INTO hist_table (LOCATION, OBSERVATION_TIME, POINTS) VALUES (?, ?, ?)",
        [("loc", f"2020-01-01 00:{i % 60:02d}:00", payload) for i in range(rows)])
    conn.commit()


def test_page_count_matches_pragma_page_count_minus_freelist_count(hist_cache):
    cache = hist_cache
    conn = cache._sqlite_conn
    cursor = conn.cursor()
    _fill_hist_table(conn)

    # Delete the oldest half so freelist_count is nonzero: page_count alone
    # would not exercise the subtraction the fix depends on.
    cursor.execute(
        "DELETE FROM hist_table WHERE ID IN "
        "(SELECT ID FROM hist_table ORDER BY ID ASC LIMIT 125)")
    conn.commit()

    expected_page_count, expected_freelist_count = _pragma_used_pages(conn)
    assert expected_freelist_count > 0, (
        "test setup did not free any pages; strengthen the delete above")

    actual = WeatherCache.page_count(cursor)

    assert actual == expected_page_count - expected_freelist_count
    cache.close()


def test_manage_cache_size_terminates_and_logs_when_nothing_can_be_trimmed(
        hist_cache, caplog):
    # Empty tables so no deletion can ever bring page_count below max_pages.
    # Pre-fix, the second (untargeted) trim loop had no exit condition other
    # than page_count dropping below max_pages, and PRAGMA page_count never
    # drops without a VACUUM: against unfixed code this spins forever.
    cache = hist_cache
    cache._max_size_gb = 1
    cache._max_pages = 0

    with caplog.at_level(logging.WARNING,
                         logger="volttron.platform.agent.base_weather"):
        cache.manage_cache_size()

    assert "no more records can be deleted" in caplog.text
    cache.close()


def test_manage_cache_size_trims_oldest_and_commits(hist_cache, tmp_path):
    cache = hist_cache
    conn = cache._sqlite_conn
    cursor = conn.cursor()
    _fill_hist_table(conn)

    used_before = WeatherCache.page_count(cursor)
    # One page below current usage: any real trim satisfies the threshold,
    # so the loop exits after the single oldest-100 deletion round rather
    # than exhausting every row.
    cache._max_size_gb = 1
    cache._max_pages = used_before - 1

    cache.manage_cache_size()
    cache.close()

    # Read back on a fresh connection: the assertion must see what a later
    # process opening this file would see, not the writer's own cursor.
    fresh = sqlite3.connect(str(tmp_path / "weather.sqlite"))
    fresh_cursor = fresh.cursor()
    fresh_cursor.execute(
        "SELECT MIN(ID), MAX(ID), COUNT(*) FROM hist_table")
    min_id, max_id, count = fresh_cursor.fetchone()

    assert count == 150
    assert min_id == 101, "the oldest 100 rows (lowest IDs) should be gone"
    assert max_id == 250, "the newest rows should be the ones kept"

    used_after = WeatherCache.page_count(fresh_cursor)
    assert used_after < cache._max_pages
    fresh.close()


# ---------------------------------------------------------------------------
# Cache-full reporting, trim hysteresis, timed deletes and status handling.
# ---------------------------------------------------------------------------

import datetime
from types import SimpleNamespace

from volttron.platform.agent.base_weather import BaseWeatherAgent, CACHE_FULL, quote_identifier
from volttron.platform.agent.utils import get_aware_utc_now
from volttron.platform.messaging.health import STATUS_BAD, STATUS_GOOD, Status

UTC = datetime.timezone.utc
HIST = {"hist_table": {"type": "history", "update_interval": None,
                       "description": None}}


def _fill_history(cache, n=250, payload_size=500):
    conn = cache._sqlite_conn
    rows = [("loc", datetime.datetime(2020, 1, 1, tzinfo=UTC)
             + datetime.timedelta(minutes=i), "x" * payload_size)
            for i in range(n)]
    conn.executemany(
        "INSERT INTO hist_table (LOCATION, OBSERVATION_TIME, POINTS) "
        "VALUES (?, ?, ?)", rows)
    conn.commit()
    return WeatherCache.page_count(conn.cursor())


def _set_limit(cache, max_pages):
    cache._max_size_gb = 1
    cache._max_pages = max_pages


def test_store_reports_full_only_when_trim_cannot_free_space(tmp_path):
    cache = _make_cache(tmp_path, dict(HIST))
    used = _fill_history(cache)
    _set_limit(cache, used)      # exactly at the limit

    record = ("loc", datetime.datetime(2021, 1, 1, tzinfo=UTC), "x" * 500)
    full = cache.store_weather_records("hist_table", [record])

    assert full is False, "trim freed space, so the cache is not full"
    assert WeatherCache.page_count(cache._sqlite_conn.cursor()) < used

    # Nothing can satisfy a zero-page limit: now it really is full.
    _set_limit(cache, 0)
    assert cache.store_weather_records("hist_table", [record]) is True
    cache.close()


def test_trim_goes_to_low_water_mark_not_just_under_limit(tmp_path):
    cache = _make_cache(tmp_path, dict(HIST))
    used = _fill_history(cache, n=2000)
    _set_limit(cache, used)

    cache.manage_cache_size()

    after = WeatherCache.page_count(cache._sqlite_conn.cursor())
    assert after < int(used * WeatherCache.TRIM_TARGET_FRACTION)
    cache.close()


def test_expired_current_records_removed_and_fresh_kept(tmp_path):
    api_services = {"cur_table": {"type": "current",
                                  "update_interval": datetime.timedelta(hours=1),
                                  "description": None}}
    cache = _make_cache(tmp_path, api_services)
    conn = cache._sqlite_conn
    now = get_aware_utc_now()
    old = now - datetime.timedelta(days=2)
    rows = []
    for i in range(300):
        rows.append(("loc", old + datetime.timedelta(seconds=i), "x" * 300))
        rows.append(("loc", now, "fresh"))
    conn.executemany(
        "INSERT INTO cur_table (LOCATION, OBSERVATION_TIME, POINTS) "
        "VALUES (?, ?, ?)", rows)
    conn.commit()
    cursor = conn.cursor()
    _set_limit(cache, WeatherCache.page_count(cursor) - 1)

    cache.manage_cache_size()

    cursor.execute("SELECT COUNT(*), SUM(POINTS = 'fresh') FROM cur_table")
    assert cursor.fetchone() == (300, 300)
    cache.close()


def test_expired_forecast_records_removed_and_fresh_kept(tmp_path):
    api_services = {"fc_table": {"type": "forecast",
                                 "update_interval": datetime.timedelta(hours=1),
                                 "description": None}}
    cache = _make_cache(tmp_path, api_services)
    conn = cache._sqlite_conn
    now = get_aware_utc_now()
    # Rows written by older code carry naive timestamps; they must still
    # compare correctly against the aware cutoff.
    old = (now - datetime.timedelta(days=2)).replace(tzinfo=None)
    rows = [("loc", old, old + datetime.timedelta(hours=h), "y" * 300)
            for h in range(300)]
    rows += [("loc", now, now + datetime.timedelta(hours=h), "fresh")
             for h in range(5)]
    conn.executemany(
        "INSERT INTO fc_table (LOCATION, GENERATION_TIME, FORECAST_TIME, "
        "POINTS) VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    cursor = conn.cursor()
    _set_limit(cache, WeatherCache.page_count(cursor) - 1)

    cache.manage_cache_size()

    cursor.execute("SELECT COUNT(*), SUM(POINTS = 'fresh') FROM fc_table")
    assert cursor.fetchone() == (5, 5)
    cache.close()


def test_unset_update_interval_falls_through_to_oldest_first(tmp_path):
    # Before onstart, update_interval is None for every service. The timed
    # delete must be skipped (no TypeError) and the oldest-first pass must
    # trim the table instead.
    api_services = {"cur_table": {"type": "current", "update_interval": None,
                                  "description": None}}
    cache = _make_cache(tmp_path, api_services)
    conn = cache._sqlite_conn
    rows = [("loc", datetime.datetime(2020, 1, 1, tzinfo=UTC)
             + datetime.timedelta(minutes=i), "x" * 500) for i in range(250)]
    conn.executemany(
        "INSERT INTO cur_table (LOCATION, OBSERVATION_TIME, POINTS) "
        "VALUES (?, ?, ?)", rows)
    conn.commit()
    _set_limit(cache, WeatherCache.page_count(conn.cursor()) - 1)

    cache.manage_cache_size()
    cache.close()

    fresh = sqlite3.connect(str(tmp_path / "weather.sqlite"))
    cursor = fresh.cursor()
    cursor.execute("SELECT MIN(ID), MAX(ID), COUNT(*) FROM cur_table")
    assert cursor.fetchone() == (101, 250, 150)
    fresh.close()


def test_oldest_first_batch_doubles_and_rounds_are_capped(tmp_path, caplog):
    cache = _make_cache(tmp_path, dict(HIST))
    _fill_history(cache, n=1000, payload_size=1)
    cache.TRIM_MAX_ROUNDS = 2
    _set_limit(cache, 0)

    with caplog.at_level(logging.ERROR,
                         logger="volttron.platform.agent.base_weather"):
        cache.manage_cache_size()

    cursor = cache._sqlite_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM hist_table")
    # Two rounds of 100 then 200 rows; hitting the round cap ends trimming
    # rather than starting the all-tables pass.
    assert cursor.fetchone()[0] == 1000 - (100 + 200)
    assert "exceeded max attempts" in caplog.text
    cache.close()


class _FakeHealth:
    def __init__(self):
        self.status = Status.build(STATUS_GOOD)
        self.alerts = []

    def set_status(self, status, context=None):
        self.status.update_status(status, context)

    def get_status_json(self):
        return self.status.as_json()

    def get_status(self):
        return self.status.as_dict()

    def send_alert(self, key, status):
        self.alerts.append(key)


def _agent_stub(results):
    """A stand-in for BaseWeatherAgent with only what store_weather_records
    touches, and a cache whose store call returns the given values in order."""
    results = list(results)
    cache = SimpleNamespace(
        store_weather_records=lambda *_: results.pop(0))
    agent = SimpleNamespace(_cache=cache, vip=SimpleNamespace(health=_FakeHealth()),
                            cache_write_error=False, cache_full=False)
    agent._clear_status_set_here = (
        lambda context: BaseWeatherAgent._clear_status_set_here(agent, context))
    return agent


def test_successful_write_does_not_clear_unrelated_bad_status():
    agent = _agent_stub([False])
    agent.vip.health.set_status(STATUS_BAD, "Weather agent failed to read from cache")

    BaseWeatherAgent.store_weather_records(agent, "svc", [])

    assert agent.vip.health.status.status == STATUS_BAD
    assert agent.vip.health.alerts == []


def test_cache_full_status_is_set_then_cleared_by_this_path_only():
    agent = _agent_stub([True, True, False])
    health = agent.vip.health

    BaseWeatherAgent.store_weather_records(agent, "svc", [])
    assert health.status.status == STATUS_BAD
    assert health.alerts == [CACHE_FULL]
    assert agent.cache_full is True

    BaseWeatherAgent.store_weather_records(agent, "svc", [])
    assert health.alerts == [CACHE_FULL, CACHE_FULL]

    BaseWeatherAgent.store_weather_records(agent, "svc", [])
    assert health.status.status == STATUS_GOOD
    assert agent.cache_full is False


def test_cache_full_recovery_leaves_a_newer_unrelated_bad_status_alone():
    """Cache fills (BAD, cache_full flag set), then another path reports its
    own fault. When the cache recovers it must not wipe that newer status."""
    agent = _agent_stub([True, False])
    health = agent.vip.health

    BaseWeatherAgent.store_weather_records(agent, "svc", [])
    assert health.status.status == STATUS_BAD
    health.set_status(STATUS_BAD, "Weather API unreachable")

    BaseWeatherAgent.store_weather_records(agent, "svc", [])

    assert agent.cache_full is False
    assert health.status.status == STATUS_BAD
    assert health.status.context == "Weather API unreachable"


@pytest.mark.parametrize("bad_name", ["bad name", 'x"; DROP TABLE y; --', "1table", "", None])
def test_cache_rejects_service_names_that_are_not_plain_identifiers(tmp_path, bad_name):
    with pytest.raises(ValueError):
        _make_cache(tmp_path, {bad_name: {"type": "history", "update_interval": None,
                                          "description": None}})


def test_register_service_rejects_names_that_are_not_plain_identifiers():
    agent = SimpleNamespace(_api_services={})
    with pytest.raises(ValueError, match="plain identifier"):
        BaseWeatherAgent.register_service(agent, 'x"; DROP TABLE y; --', None, "history")
    BaseWeatherAgent.register_service(agent, "get_hourly_historical", None, "history")
    assert "get_hourly_historical" in agent._api_services


def test_quote_identifier_quotes_plain_names():
    assert quote_identifier("hist_table") == '"hist_table"'
    assert quote_identifier("API_CALLS") == '"API_CALLS"'
