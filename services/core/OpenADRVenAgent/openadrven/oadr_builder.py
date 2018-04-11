# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

from datetime import datetime as dt
from datetime import timedelta
import isodate
import json
import logging
import uuid

from volttron.platform.agent import utils

import oadr_20b
from oadr_common import *

utils.setup_logging()
_log = logging.getLogger(__name__)


class OadrBuilder(object):
    """Abstract superclass. Build oadr model objects to send to the VTN."""

    def __init__(self, request_id=None, ven_id=None, **kwargs):
        self.request_id = request_id
        self.ven_id = ven_id

    @staticmethod
    def create_request_id():
        return uuid.uuid1()


class OadrPollBuilder(OadrBuilder):

    def __init__(self, **kwargs):
        super(OadrPollBuilder, self).__init__(**kwargs)

    def build(self):
        return oadr_20b.oadrPollType(schemaVersion=SCHEMA_VERSION, venID=self.ven_id)


class OadrQueryRegistrationBuilder(OadrBuilder):

    def __init__(self, **kwargs):
        super(OadrQueryRegistrationBuilder, self).__init__(**kwargs)

    def build(self):
        return oadr_20b.oadrQueryRegistrationType(schemaVersion=SCHEMA_VERSION, requestID=self.create_request_id())


class OadrCreatePartyRegistrationBuilder(OadrBuilder):

    def __init__(self, xml_signature=None, ven_name=None, **kwargs):
        super(OadrCreatePartyRegistrationBuilder, self).__init__(**kwargs)
        self.xml_signature = xml_signature
        self.ven_name = ven_name

    def build(self):
        return oadr_20b.oadrCreatePartyRegistrationType(schemaVersion=SCHEMA_VERSION,
                                                        requestID=self.create_request_id(),
                                                        registrationID=None,
                                                        venID=self.ven_id,
                                                        oadrProfileName='2.0b',
                                                        oadrTransportName='simpleHttp',
                                                        oadrTransportAddress=None,
                                                        oadrReportOnly=False,
                                                        oadrXmlSignature=self.xml_signature,
                                                        oadrVenName=self.ven_name,
                                                        oadrHttpPullModel=True)


class OadrRequestEventBuilder(OadrBuilder):

    def __init__(self, **kwargs):
        super(OadrRequestEventBuilder, self).__init__(**kwargs)

    def build(self):
        ei_request_event = oadr_20b.eiRequestEvent(requestID=self.create_request_id(), venID=self.ven_id)
        return oadr_20b.oadrRequestEventType(schemaVersion=SCHEMA_VERSION, eiRequestEvent=ei_request_event)


class OadrCreatedEventBuilder(OadrBuilder):

    """
        Construct an oadrCreatedEvent to return in response to an oadrDistributeEvent or oadrCreateEvent.

        If an error occurs while processing an events in the VTN's payload, return an oadrCreatedEvent
        response in which the eiResponse has a normal/valid (200) code,
        and the eventResponse has a responseCode containing the error code.
    """

    def __init__(self, event=None, error_code=None, error_message=None, **kwargs):
        super(OadrCreatedEventBuilder, self).__init__(**kwargs)
        self.event = event
        self.error_code = error_code
        self.error_message = error_message

    def build(self):
        ei_response = oadr_20b.EiResponseType(responseCode=OADR_VALID_RESPONSE, requestID=None)
        qualified_event_id = oadr_20b.QualifiedEventIDType(eventID=self.event.event_id,
                                                           modificationNumber=self.event.modification_number)
        # OADR rule 42: the requestID from the oadrDistributeEvent must be re-used by the eventResponse.
        event_response = oadr_20b.eventResponseType(responseCode=self.error_code or OADR_VALID_RESPONSE,
                                                    responseDescription=self.error_message,
                                                    requestID=self.event.request_id,
                                                    qualifiedEventID=qualified_event_id,
                                                    optType=self.event.opt_type)
        # OADR rule 25, 35: eventResponses is required except when eiResponse indicates failure.
        event_responses = oadr_20b.eventResponses()
        event_responses.add_eventResponse(event_response)
        ei_created_event = oadr_20b.eiCreatedEvent(eiResponse=ei_response,
                                                   eventResponses=event_responses,
                                                   venID=self.ven_id)
        return oadr_20b.oadrCreatedEventType(eiCreatedEvent=ei_created_event)


class OadrReportBuilder(OadrBuilder):

    def __init__(self, report=None, report_request_id=None, pending_report_request_ids=None, **kwargs):
        super(OadrReportBuilder, self).__init__(**kwargs)
        self.report = report
        self.report_request_id = report_request_id
        self.pending_report_request_ids = pending_report_request_ids


class OadrRegisterReportBuilder(OadrReportBuilder):

    def __init__(self, reports=None, **kwargs):
        super(OadrRegisterReportBuilder, self).__init__(**kwargs)
        self.reports = reports

    def build(self):
        oadr_reports = [self.build_metadata_oadr_report(report) for report in self.reports]
        return oadr_20b.oadrRegisterReportType(schemaVersion=SCHEMA_VERSION,
                                               requestID=self.create_request_id(),
                                               oadrReport=oadr_reports,
                                               venID=self.ven_id,
                                               reportRequestID=None)

    def build_metadata_oadr_report(self, report):
        descriptions = []
        for tel_vals in json.loads(report.telemetry_parameters).values():
            # Rule 305: For TELEMETRY_USAGE reports, units in reportDescription.itemBase should be powerReal.
            if tel_vals['units'] == 'powerReal':
                item_base = oadr_20b.PowerRealType(itemDescription='RealPower',
                                                   itemUnits='W',
                                                   siScaleCode=None,
                                                   powerAttributes=None)
            else:
                item_base = None
            min_freq, max_freq = tel_vals['min_frequency'], tel_vals['max_frequency']
            desc = oadr_20b.oadrReportDescriptionType(rID=tel_vals['r_id'],
                                                      reportType=tel_vals['report_type'],
                                                      readingType=tel_vals['reading_type'],
                                                      itemBase=item_base,
                                                      oadrSamplingRate=self.build_sampling_rate(min_freq, max_freq))
            descriptions.append(desc)
        rpt_interval_duration = isodate.duration_isoformat(timedelta(seconds=report.interval_secs))
        return oadr_20b.oadrReportType(duration=oadr_20b.DurationPropType(rpt_interval_duration),
                                       oadrReportDescription=descriptions,
                                       reportRequestID=None,
                                       reportSpecifierID=report.report_specifier_id,
                                       reportName=report.name,
                                       createdDateTime=utils.get_aware_utc_now())

    @staticmethod
    def build_sampling_rate(min_freq, max_freq):
        min_sampling_rate = isodate.duration_isoformat(timedelta(seconds=min_freq))
        max_sampling_rate = isodate.duration_isoformat(timedelta(seconds=max_freq))
        sampling_rate = oadr_20b.oadrSamplingRateType(oadrMinPeriod=min_sampling_rate,
                                                      oadrMaxPeriod=max_sampling_rate,
                                                      oadrOnChange=False)
        return sampling_rate


class OadrUpdateReportBuilder(OadrReportBuilder):

    def __init__(self, telemetry=None, online=None, manual_override=None, **kwargs):
        super(OadrUpdateReportBuilder, self).__init__(**kwargs)
        self.telemetry = telemetry
        self.online = online
        self.manual_override = manual_override

    def build(self):
        """
            Return an oadrReport containing telemetry updates.

            A typical XML element structure is:

            <oadr:oadrReport>
                <xcal:dtstart>
                    <xcal:date-time>2017-12-06T21:33:32Z</xcal:date-time>
                </xcal:dtstart>
                <xcal:duration>
                    <oadr:duration>PT0S</oadr:duration>
                </xcal:duration>
                <strm:intervals>
                    <ei:interval>
                        <xcal:dtstart>
                            <xcal:date-time>2017-12-06T21:33:08.423684Z</xcal:date-time>
                        </xcal:dtstart>
                        <xcal:duration>
                            <oadr:duration>PT30S</oadr:duration>
                        </xcal:duration>
                        <oadr:oadrReportPayload>
                            <ei:rID>baseline_power</ei:rID>
                            <ei:payloadFloat>
                                <ei:value>6.2</ei:value>
                            </ei:payloadFloat>
                        </oadr:oadrReportPayload>
                        <oadr:oadrReportPayload>
                            <ei:rID>actual_power</ei:rID>
                            <ei:payloadFloat>
                                <ei:value>5.44668467252</ei:value>
                            </ei:payloadFloat>
                        </oadr:oadrReportPayload>
                        <oadr:oadrReportPayload>
                            <ei:rID>Status</ei:rID>
                            <oadr:oadrPayloadResourceStatus>
                                <oadr:oadrOnline>true</oadr:oadrOnline>
                                <oadr:oadrManualOverride>false</oadr:oadrManualOverride>
                            </oadr:oadrPayloadResourceStatus>
                        </oadr:oadrReportPayload>
                    </ei:interval>
                </strm:intervals>
                <ei:reportRequestID>RR_916fd571c0657070575a</ei:reportRequestID>
                <ei:reportSpecifierID>telemetry</ei:reportSpecifierID>
                <ei:reportName>TELEMETRY_USAGE</ei:reportName>
                <ei:createdDateTime>2017-12-06T21:33:47.869392Z</ei:createdDateTime>
            </oadr:oadrReport>

        @return: (oadrReportType) An oadrReport.
        """
        # To accommodate the Kisensum VTN server, a null report duration has a special meaning
        # to the VEN: the report request should continue indefinitely, with no scheduled
        # completion time.
        # In this UpdateReport request, a null duration is sent as 0 seconds (one-time report)
        # to ensure that the UpdateReport has a valid construction.
        report_duration = self.report.duration if self.report.duration is not None else 'PT0S'
        oadr_report = oadr_20b.oadrReportType(dtstart=oadr_20b.dtstart(date_time=self.report.start_time),
                                              duration=oadr_20b.DurationPropType(report_duration),
                                              reportRequestID=self.report.report_request_id,
                                              reportSpecifierID=self.report.report_specifier_id,
                                              reportName=self.report.name,
                                              intervals=self.build_intervals(),
                                              createdDateTime=utils.get_aware_utc_now())
        return oadr_20b.oadrUpdateReportType(schemaVersion=SCHEMA_VERSION,
                                             requestID=self.create_request_id(),
                                             oadrReport=[oadr_report],
                                             venID=self.ven_id)

    def build_intervals(self):
        """Build an intervals object, holding a list of Intervals to report in this update."""
        intervals = oadr_20b.intervals()
        if self.report.report_specifier_id == 'telemetry':
            # Build Intervals that report metrics.
            for telemetry_values in self.telemetry:
                intervals.add_interval(self.build_report_interval(telemetry_values))
        elif self.report.report_specifier_id == 'telemetry_status':
            # OADR rule 331, 510: Build an Interval, in a telemetry_status report, giving current VEN status.
            interval_start = isodate.parse_datetime(self.report.iso_last_report)
            interval_duration = isodate.duration_isoformat(timedelta(seconds=self.report.interval_secs))
            interval = oadr_20b.IntervalType(dtstart=oadr_20b.dtstart(date_time=interval_start),
                                             duration=oadr_20b.DurationPropType(duration=interval_duration))
            if self.online is not None or self.manual_override is not None:
                payload = oadr_20b.oadrReportPayloadType(rID='Status')
                payload_status = oadr_20b.oadrPayloadResourceStatusType(oadrOnline=self.online,
                                                                        oadrManualOverride=self.manual_override)
                payload_status.original_tagname_ = 'oadrPayloadResourceStatus'
                payload.set_payloadBase(payload_status)
                interval.set_streamPayloadBase([payload])
            else:
                interval.set_streamPayloadBase([])
            intervals.add_interval(interval)
        return intervals

    def build_report_interval(self, telemetry_values):
        """Build an Interval for a report timeframe that includes telemetry values gathered during that time."""
        interval_start = telemetry_values.start_time
        # duration_isoformat can yield fractional seconds, e.g. PT59.9S, resulting in a warning during XML creation.
        interval_duration = isodate.duration_isoformat(telemetry_values.get_duration())
        interval = oadr_20b.IntervalType(dtstart=oadr_20b.dtstart(date_time=interval_start),
                                         duration=oadr_20b.DurationPropType(duration=interval_duration))
        interval.set_streamPayloadBase(self.build_report_payload_list(telemetry_values))
        return interval

    def build_report_payload_list(self, telemetry_values):
        """Build a list of ReportPayloads containing current telemetry."""
        report_payload_list = []
        for tel_val in json.loads(self.report.telemetry_parameters).values():
            payload = self.build_report_payload_float(telemetry_values, tel_val['r_id'], tel_val['method_name'])
            if payload:
                report_payload_list.append(payload)
        return report_payload_list

    @staticmethod
    def build_report_payload_float(telemetry_values, r_id, method_name):
        """Build a single ReportPayload containing a PayloadFloat metric."""
        metric = getattr(telemetry_values, method_name)()
        if metric is None:
            payload = None
        else:
            payload = oadr_20b.oadrReportPayloadType(rID=r_id)
            payload.original_tagname_ = 'oadrReportPayload'
            payload_float = oadr_20b.PayloadFloatType(value=metric)
            payload_float.original_tagname_ = 'payloadFloat'
            payload.set_payloadBase(payload_float)
        return payload


class OadrCreatedReportBuilder(OadrReportBuilder):

    def __init__(self, **kwargs):
        super(OadrCreatedReportBuilder, self).__init__(**kwargs)

    def build(self):
        ei_response = oadr_20b.EiResponseType(responseCode=OADR_VALID_RESPONSE, requestID=self.create_request_id())
        oadr_pending_reports = oadr_20b.oadrPendingReportsType(reportRequestID=self.pending_report_request_ids)
        return oadr_20b.oadrCreatedReportType(schemaVersion=SCHEMA_VERSION,
                                              eiResponse=ei_response,
                                              oadrPendingReports=oadr_pending_reports,
                                              venID=self.ven_id)


class OadrCanceledReportBuilder(OadrReportBuilder):

    def __init__(self, **kwargs):
        super(OadrCanceledReportBuilder, self).__init__(**kwargs)

    def build(self):
        # Note that -- oddly -- this message does NOT contain the reportRequestID of the canceled report.
        # It does list all active reports in oadrPendingReports, though,
        # so the VTN has sufficient information to know which report was canceled.
        ei_response = oadr_20b.EiResponseType(responseCode=OADR_VALID_RESPONSE, requestID=self.request_id)
        oadr_pending_reports = oadr_20b.oadrPendingReportsType(reportRequestID=self.pending_report_request_ids)
        return oadr_20b.oadrCanceledReportType(schemaVersion=SCHEMA_VERSION,
                                               eiResponse=ei_response,
                                               oadrPendingReports=oadr_pending_reports,
                                               venID=self.ven_id)


class OadrResponseBuilder(OadrBuilder):

    def __init__(self, response_code=None, response_description=None, **kwargs):
        super(OadrResponseBuilder, self).__init__(**kwargs)
        self.response_code = response_code
        self.response_description = response_description

    def build(self):
        ei_response = oadr_20b.EiResponseType(responseCode=self.response_code,
                                              responseDescription=self.response_description,
                                              requestID=self.request_id)
        return oadr_20b.oadrResponseType(schemaVersion=SCHEMA_VERSION,
                                         eiResponse=ei_response,
                                         venID=self.ven_id)
