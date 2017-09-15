# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
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

    def __init__(self, event=None, **kwargs):
        super(OadrCreatedEventBuilder, self).__init__(**kwargs)
        self.event = event

    def build(self):
        ei_response = oadr_20b.EiResponseType(responseCode=OADR_VALID_RESPONSE, requestID=self.event.request_id)
        qualified_event_id = oadr_20b.QualifiedEventIDType(eventID=self.event.event_id,
                                                           modificationNumber=self.event.modification_number)
        # OADR rule 42: the requestID from the oadrDistributeEvent must be re-used by the eventResponse.
        event_response = oadr_20b.eventResponseType(responseCode=OADR_VALID_RESPONSE,
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

    def __init__(self, report=None, report_request_id=None, **kwargs):
        super(OadrReportBuilder, self).__init__(**kwargs)
        self.report = report
        self.report_request_id = report_request_id

    def telemetry_parameters(self):
        return json.loads(self.report.telemetry_parameters)


class OadrRegisterReportBuilder(OadrReportBuilder):

    def __init__(self, **kwargs):
        super(OadrRegisterReportBuilder, self).__init__(**kwargs)

    def build(self):
        descriptions = []
        for tel_vals in self.telemetry_parameters().values():
            desc = oadr_20b.oadrReportDescriptionType(rID=tel_vals['r_id'],
                                                      reportType=tel_vals['report_type'],
                                                      readingType=tel_vals['reading_type'],
                                                      oadrSamplingRate=self.build_sampling_rate(tel_vals['frequency']))
            descriptions.append(desc)
        # oadrPayloadResourceStatus is hard-coded -- add it to the descriptions.
        desc = oadr_20b.oadrReportDescriptionType(rID='Status',
                                                  reportType='x-resourceStatus',
                                                  readingType='x-notApplicable',
                                                  oadrSamplingRate=self.build_sampling_rate(60))
        descriptions.append(desc)
        rpt_interval_duration = isodate.duration_isoformat(timedelta(seconds=self.report.interval_secs))
        oadr_report = oadr_20b.oadrReportType(duration=oadr_20b.DurationPropType(rpt_interval_duration),
                                              oadrReportDescription=descriptions,
                                              reportRequestID=None,
                                              reportSpecifierID=self.report.report_specifier_id,
                                              reportName=self.report.name,
                                              createdDateTime=utils.get_aware_utc_now())
        return oadr_20b.oadrRegisterReportType(schemaVersion=SCHEMA_VERSION,
                                               requestID=self.create_request_id(),
                                               oadrReport=[oadr_report],
                                               venID=self.ven_id,
                                               reportRequestID=None)

    @staticmethod
    def build_sampling_rate(rate):
        min_sampling_rate = isodate.duration_isoformat(timedelta(seconds=rate))
        max_sampling_rate = isodate.duration_isoformat(timedelta(seconds=rate))
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
        intervals = oadr_20b.intervals()
        for telemetry_values in self.telemetry:
            intervals.add_interval(self.build_report_interval(telemetry_values))
        # To accommodate the Kisensum VTN server, a null duration in the report interval
        # has a special meaning to the VEN: the report request should continue indefinitely,
        # with no scheduled completion time. In this UpdateReport request, a null duration is sent
        # as 0 seconds (one-time report) to ensure that the UpdateReport has a valid construction.
        report_duration = self.report.duration if self.report.duration is not None else 'PT0S'
        oadr_report = oadr_20b.oadrReportType(dtstart=oadr_20b.dtstart(date_time=self.report.start_time),
                                              duration=oadr_20b.DurationPropType(report_duration),
                                              reportRequestID=self.report.report_request_id,
                                              reportSpecifierID=self.report.report_specifier_id,
                                              reportName=self.report.name,
                                              intervals=intervals,
                                              createdDateTime=utils.get_aware_utc_now())
        return oadr_20b.oadrUpdateReportType(schemaVersion=SCHEMA_VERSION,
                                             requestID=self.create_request_id(),
                                             oadrReport=[oadr_report],
                                             venID=self.ven_id)

    def build_report_interval(self, telemetry_values):
        """Build an Interval for a report timeframe that includes telemetry values gathered during that time."""
        dtstart = oadr_20b.dtstart(date_time=telemetry_values.start_time)
        # duration_isoformat can yield fractional seconds, e.g. PT59.9S, resulting in a warning during XML creation.
        duration = oadr_20b.DurationPropType(duration=isodate.duration_isoformat(telemetry_values.get_duration()))
        report_payload_list = self.build_report_payload_list(telemetry_values)
        interval = oadr_20b.IntervalType(dtstart=dtstart, duration=duration)
        interval.set_streamPayloadBase(report_payload_list)
        return interval

    def build_report_payload_list(self, telemetry_values):
        """Build a list of ReportPayloads containing telemetry values to be reported."""
        report_payload_list = []
        for tel_val in self.telemetry_parameters().values():
            metric = getattr(telemetry_values, tel_val['method_name'])()
            if metric is not None:
                payload = oadr_20b.oadrReportPayloadType(rID=tel_val['r_id'])
                payload.original_tagname_ = 'oadrReportPayload'
                payload_float = oadr_20b.PayloadFloatType(value=metric)
                payload_float.original_tagname_ = 'payloadFloat'
                payload.set_payloadBase(payload_float)
                report_payload_list.append(payload)
        if self.online is not None or self.manual_override is not None:
            payload = oadr_20b.oadrReportPayloadType(rID='Status')
            payload.original_tagname_ = 'oadrReportPayload'
            payload_status = oadr_20b.oadrPayloadResourceStatusType(oadrOnline=self.online,
                                                                    oadrManualOverride=self.manual_override)
            payload_status.original_tagname_ = 'oadrPayloadResourceStatus'
            payload.set_payloadBase(payload_status)
            report_payload_list.append(payload)
        return report_payload_list


class OadrCreatedReportBuilder(OadrReportBuilder):

    def __init__(self, **kwargs):
        super(OadrCreatedReportBuilder, self).__init__(**kwargs)

    def build(self):
        ei_response = oadr_20b.EiResponseType(responseCode=OADR_VALID_RESPONSE, requestID=self.create_request_id())
        oadr_pending_reports = oadr_20b.oadrPendingReportsType(reportRequestID=[self.report_request_id])
        return oadr_20b.oadrCreatedReportType(schemaVersion=SCHEMA_VERSION,
                                              eiResponse=ei_response,
                                              oadrPendingReports=oadr_pending_reports,
                                              venID=self.ven_id)


class OadrCanceledReportBuilder(OadrReportBuilder):

    def __init__(self, **kwargs):
        super(OadrCanceledReportBuilder, self).__init__(**kwargs)

    def build(self):
        ei_response = oadr_20b.EiResponseType(responseCode=OADR_VALID_RESPONSE, requestID=self.request_id)
        oadr_pending_reports = oadr_20b.oadrPendingReportsType(reportRequestID=[self.report_request_id])
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
