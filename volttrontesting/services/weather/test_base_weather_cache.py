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


def test_page_count_matches_pragma_page_count_minus_freelist_count(tmp_path):
    api_services = {
        "hist_table": {"type": "history", "update_interval": None,
                       "description": None},
    }
    cache = _make_cache(tmp_path, api_services)
    conn = cache._sqlite_conn
    cursor = conn.cursor()

    payload = "x" * 500
    rows = [("loc", f"2020-01-01 00:{i % 60:02d}:00", payload)
            for i in range(250)]
    cursor.executemany(
        "INSERT INTO hist_table (LOCATION, OBSERVATION_TIME, POINTS) "
        "VALUES (?, ?, ?)", rows)
    conn.commit()

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
        tmp_path, caplog):
    # Empty tables so no deletion can ever bring page_count below max_pages.
    # Pre-fix, the second (untargeted) trim loop had no exit condition other
    # than page_count dropping below max_pages, and PRAGMA page_count never
    # drops without a VACUUM: against unfixed code this spins forever.
    api_services = {
        "hist_table": {"type": "history", "update_interval": None,
                       "description": None},
    }
    cache = _make_cache(tmp_path, api_services)
    cache._max_size_gb = 1
    cache._max_pages = 0

    with caplog.at_level(logging.WARNING,
                         logger="volttron.platform.agent.base_weather"):
        cache.manage_cache_size()

    assert "no more records can be deleted" in caplog.text
    cache.close()


def test_manage_cache_size_trims_oldest_and_commits(tmp_path):
    api_services = {
        "hist_table": {"type": "history", "update_interval": None,
                       "description": None},
    }
    cache = _make_cache(tmp_path, api_services)
    conn = cache._sqlite_conn
    cursor = conn.cursor()

    payload = "x" * 500
    rows = [("loc", f"2020-01-01 00:{i % 60:02d}:00", payload)
            for i in range(250)]
    cursor.executemany(
        "INSERT INTO hist_table (LOCATION, OBSERVATION_TIME, POINTS) "
        "VALUES (?, ?, ?)", rows)
    conn.commit()

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
