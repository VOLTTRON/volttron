# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, EnerNOC Inc
# All rights reserved.

#}}}


import sys
import logging

import pytz
import time
import json
import requests
import datetime as dt

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics

from oadr2 import poll, event, schedule, database
from lxml import etree

log = logging.getLogger(__name__)

def OpenADRAgent(config_path, **kwargs):
    config = utils.load_config(config_path)

    def get_config(name):
        try:
            value = kwargs.pop(name)
        except KeyError:
            return config[name]

    agent_id = get_config('agentid')
    ven_id = get_config('ven_id')
    vtn_uri = get_config('vtn_uri')
    poll_interval = get_config('poll_interval')
    vtn_ids = get_config('vtn_ids')
    control_interval = get_config('control_interval')
    
    smap_uri = get_config('smap_uri')
    smap_source_name = get_config('smap_source_name')
    smap_series_uuid = get_config('smap_series_uuid')
    smap_source_location = get_config('smap_source_location')
    
    event_db = database.DBHandler()

    class Agent(PublishMixin, BaseAgent):
        '''
        This agent acts as an OpenADR VEN and publishes oadrDistributeEvent
        messages to the bus
        '''

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.events = dict()
            self.oadr_client = poll.OpenADR2(
                    vtn_base_uri = vtn_uri,
                    vtn_poll_interval = poll_interval,
                    event_config = {
                        "ven_id" : ven_id,
                        "vtn_ids": vtn_ids,
                        "event_callback": self.oadr_event
                        },
                    control_opts = {
                        "signal_changed_callback" : self.signal_changed_callback,
                        "control_loop_interval" : control_interval 
                        }
                    )

        def signal_changed_callback(self, old_level, new_level):
            '''
            This is called whenever the `oadr2.control.EventController` 
            detects a change in "current signal level" based on active
            OpenADR2 events.
            '''
            log.debug("stubbed signal change callback")
     

        def oadr_event(self, updated={}, canceled={}):
            '''Callback following VTN poll
            updated and cancelled events are passed in when present'''
            log.debug("Updated & new event(s): %s", updated)
            log.debug("Canceled event(s): %s", canceled)
            
            headers = {
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
                'requesterID': agent_id
            }

            for event_id, payload in updated.iteritems():
                event_data = self.build_event_info(payload)
                self.publish_json(topics.OPENADR_EVENT, 
                        headers, 
                        event_data )

            for event_id, payload in canceled.iteritems():
                event_data = self.build_event_info(payload)
                event_data['status'] = "cancelled"
                self.publish_json(topics.OPENADR_EVENT, 
                        headers, 
                        event_data )
                        
            current_event_state = self.get_event_state()
            self.post_to_smap(current_event_state)
            self.publish_json(topics.OPENADR_STATUS, headers,
                        { "active": (current_event_state == 'active') })
        
        # ----- temporary ----- #
        # a get_event_state method should probably be added to oadr2
        def get_event_state(self):
            active_event = None
            active_events = event_db.get_active_events()
            
            for event_id in active_events.iterkeys():
                event_data = self.get_event(event_id)
                
                e_start = event.get_active_period_start(event_data).replace(tzinfo = pytz.utc)
                now = dt.datetime.now(pytz.utc)

                if e_start < now:
                    active_event = event_data
            
            return ("active" if active_event is not None else "inactive")
        # --------------------- #
        
        # ----- temporary ----- #
        # copied from oadr.event to provide support for get_event_state above
        def get_event(self, e_id):
            evt = event_db.get_event(e_id)

            if evt is not None:
                evt = etree.XML(evt)

            return evt;
        # --------------------- #

        def build_smap_event_status_object(self, status):
            """Generate payload for POSTing current event status
            to sMAP"""
            
            status = (1 if status == 'active' else 0)
            current_time = int(time.time()) * 1000
            
            return {
                        smap_source_location: {
                            "Metadata" : {
                                "SourceName" : smap_source_name
                            },
                            "Properties" : {
                                "UnitofMeasure" : "Active/Inactive"
                            },
                            "Readings" : [[current_time, status]],
                            "uuid" : smap_series_uuid
                        }
                    }

        def post_to_smap(self, status):
            """POST updated event status info to sMAP series"""
            
            smap_payload = self.build_smap_event_status_object(status)
            
            log.debug("Updating sMAP event status: %s", status)
            r = requests.post(smap_uri, data=json.dumps(smap_payload))
            
            if r.status_code != requests.codes.ok:
                logging.warn("sMAP update unsuccessful: %s", r.status_code)
                logging.debug("sMAP update unsuccessful: %s", r.text)

        def build_event_info(self, event_xml):
            e_id = event.get_event_id(event_xml)
            e_mod_num = event.get_mod_number(event_xml)
            e_status = event.get_status(event_xml)

            # TODO get target & resource info
            event_start_dttm = event.get_active_period_start(event_xml)
            event_start_dttm = schedule.dttm_to_str(event_start_dttm)
            signals = event.get_signals(event_xml)

            # get start/end time
            start_at = event_xml.findtext(
                'ei:eiActivePeriod/xcal:properties/xcal:dtstart/xcal:date-time',
                namespaces=event.NS_A)
            start_at = schedule.str_to_datetime(start_at)
            duration = event_xml.findtext(
                'ei:eiActivePeriod/xcal:properties/xcal:duration/xcal:duration',
                namespaces=event.NS_A)
            start_at, end_at = schedule.durations_to_dates(start_at, [duration])
            
            event_info = {
                    "id"      	: e_id,
                    "mod_num" 	: e_mod_num,
                    "status"  	: e_status,
                    "start_at"	: start_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_at"	: end_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
            if signals: event_info["signals"] = signals
            
            return event_info


    Agent.__name__ = 'OpenADRAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(OpenADRAgent,
                       description='OpenADR Event agent',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

