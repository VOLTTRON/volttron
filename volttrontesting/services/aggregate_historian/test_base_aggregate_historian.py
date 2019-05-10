import pytz
from volttron.platform.agent.base_aggregate_historian import AggregateHistorian
import pytest
from datetime import datetime, timedelta


@pytest.mark.aggregator
def test_normalize_time_period():
    '''
    Test if the user given aggregation period is correctly normalized to
    correct units
    '''
    assert AggregateHistorian.normalize_aggregation_time_period('48h') == '2d'
    assert AggregateHistorian.normalize_aggregation_time_period('24h') == '1d'
    assert AggregateHistorian.normalize_aggregation_time_period('60m') == '1h'
    assert AggregateHistorian.normalize_aggregation_time_period('70m') == '70m'
    assert AggregateHistorian.normalize_aggregation_time_period('168h') == '1w'
    assert AggregateHistorian.normalize_aggregation_time_period('169h') == \
           '169h'
    assert AggregateHistorian.normalize_aggregation_time_period('7d') == '1w'
    assert AggregateHistorian.normalize_aggregation_time_period('30d') == '30d'

@pytest.mark.aggregator
def test_time_slice_calculation_calendar_time():
    '''
        Given a collection time, an aggregation time period and a boolean flag
        indicating if the time slots should align to calendar time periods or
        not, test if the AggregateHistorian is computing the correct start and
        end time for aggregation data. Start time is inclusive and end time is
        not.
        '''
    utc_collection_start_time = datetime.strptime(
        '2016-03-01T01:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)
    # Test with use_calendar_time_period = True

    #minutes aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2m', True)

    assert start.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-03-01 01:13:00.000000'
    assert end.strftime('%Y-%m-%d %H:%M:%S.%f') ==\
           '2016-03-01 01:15:00.000000'


    # hour aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '5h', True)
    assert start.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-02-29 20:00:00.000000'
    assert end.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-03-01 01:00:00.000000'

    # day aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2d', True)
    assert start.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-02-28 00:00:00.000000'
    assert end.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-03-01 00:00:00.000000'

    # week aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2w', True)
    #02-28 is the last sunday before the given collection time
    assert start.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-02-14 00:00:00.000000'
    assert end.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-02-28 00:00:00.000000'

    # month aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2M', True)
    assert start.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-02-01 00:00:00.000000'
    assert end.strftime('%Y-%m-%d %H:%M:%S.%f') == \
           '2016-02-29 00:00:00.000000'
    try:
        AggregateHistorian.compute_aggregation_time_slice(
            utc_collection_start_time, '2X', True)
    except ValueError as e:
        assert str(e) == "Invalid unit X provided for " \
                            "aggregation_period. Unit should be m/h/d/w/M"

@pytest.mark.aggregator
def test_time_slice_calculation_realtime():
    '''
    Given a collection time, an aggregation time period and a boolean flag
    indicating if the time slots should align to calendar time periods or
    not, test if the AggregateHistorian is computing the correct start and
    end time for aggregation data. Start time is inclusive and end time is
    not.
    '''
    utc_collection_start_time = datetime.strptime(
        '2016-03-01T01:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)

    # minutes aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2m', False)

    assert start == utc_collection_start_time - timedelta(minutes=2)
    assert end == utc_collection_start_time

    # hour aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '5h', False)
    assert end == utc_collection_start_time
    assert start == utc_collection_start_time - timedelta(hours=5)

    # day aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2d', False)
    assert end == utc_collection_start_time
    assert start == utc_collection_start_time - timedelta(days=2)

    # week aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2w', False)
    assert end == utc_collection_start_time
    assert start == utc_collection_start_time - timedelta(weeks=2)

    # month aggregation period
    start, end = AggregateHistorian.compute_aggregation_time_slice(
        utc_collection_start_time, '2M', False)
    print (start, end)
    assert end == utc_collection_start_time
    assert start == utc_collection_start_time - timedelta(days=60)
    try:
        AggregateHistorian.compute_aggregation_time_slice(
            utc_collection_start_time, '2X', False)
    except ValueError as e:
        assert str(e) == "Invalid unit X provided for " \
                            "aggregation_period. Unit should be m/h/d/w/M"


@pytest.mark.aggregator
def test_compute_next_collection_time():
    '''
    Test if aggregates are computed at the right interval. The interval between
    aggregation collection need not be the same as the time period for which
    aggregation is collected
    '''
    utc_collection_start_time = datetime.strptime(
        '2016-03-01T01:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)
    next1 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2m', True)
    next2 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2m', False)
    assert next1 == next2 == datetime.strptime(
        '2016-03-01T01:17:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)

    next1 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2h', True)
    next2 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2h', False)
    assert next1 == next2 == datetime.strptime(
        '2016-03-01T03:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)

    next1 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2d', True)
    next2 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2d', False)
    assert next1 == next2 == datetime.strptime(
        '2016-03-03T01:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)

    next1 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2w', True)
    next2 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2w', False)
    assert next1 == next2 == datetime.strptime(
        '2016-03-15T01:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)

    next1 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2M', True)

    # collect every 15*2 days instead of 30*2 days so that we don't end up
    # skipping February
    assert next1 == datetime.strptime(
        '2016-03-31T01:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)

    next2 = AggregateHistorian.compute_next_collection_time(
        utc_collection_start_time, '2M', False)
    assert next2 == datetime.strptime(
        '2016-04-30T01:15:23.123456',
        '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)
