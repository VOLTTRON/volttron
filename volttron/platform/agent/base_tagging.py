# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

"""
Base class for tagging service implementation. 
"""

from __future__ import absolute_import, print_function

import logging
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta

import pytz
import re
from dateutil.parser import parse
from volttron.platform.agent.utils import process_timestamp, \
    fix_sqlite3_datetime, get_aware_utc_now, parse_timestamp_string
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.vip.agent import *
from volttron.platform.vip.agent import compat

try:
    import ujson
    def dumps(data):
        return ujson.dumps(data, double_precision=15)
    def loads(data_string):
        return ujson.loads(data_string, precise_float=True)
except ImportError:
    from zmq.utils.jsonapi import dumps, loads

from volttron.platform.agent import utils

_log = logging.getLogger(__name__)

# Register a better datetime parser in sqlite3.
fix_sqlite3_datetime()



class BaseTaggingService(Agent):
    """This is the base class for tagging service implementations. There can
    be different implementations based on backend/data store used to persist 
    the tag details
    """

    def __init__(self, resource_sub_dir='resources', **kwargs):
        self.tag_categories = None
        self.resource_sub_dir = "resources"
        if resource_sub_dir:
            self.resource_sub_dir = resource_sub_dir

        super(BaseTaggingService, self).__init__(**kwargs)
        _log.debug("Done init of base tagging service")

    @Core.receiver("onstart")
    def on_start(self, sender, **kwargs):
        """
        Called on start of agent. Calls the setup method
        """
        self.setup()

    @abstractmethod
    def setup(self):
        """
        Method to establish database connection, do any initial 
        bootstrap 
        necessary. Example - load master list of tags, units, 
        categories etc.  
        into data store/memory   
        """
        pass

    @RPC.export
    def get_categories(self, skip=0, count=None, order="FIRST_TO_LAST"):
        """
        Get the available list tag categories. category can have multiple tags 
        and tags could belong to multiple categories
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        :type skip: int
        :type count: int
        :type order: str
        :return: list of category names
        :rtype: OrderedDict
        """
        _log.debug("query params: skip:{} count:{} order:{}".format(skip,
                                                                    count,
                                                                    order))
        if not self.tag_categories:
            self.tag_categories = self.query_categories(skip, count, order)
        return self.tag_categories

    @abstractmethod
    def query_categories(self, skip=0, count=None, order=None):
        pass

    @RPC.export
    def get_tags_by_category(self, category_name, skip, count, order):
        """
        Get the list of tags for a given category name. category can have multiple 
        tags and tags could belong to multiple categories
        
        :param category_name: name of the category for which associated tags 
        should be returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        :return: list of (tag names, its data type/kind)
        :type category_name: str
        :type skip: int
        :type count: int
        :type order: str
        :rtype: list
        """

        return self.query_tags_by_category(category_name, skip, count, order)

    @abstractmethod
    def query_tags_by_category(self, category_name, skip=0, count=None, order=None):
        pass

    @RPC.export
    def get_tags_by_topic(self, topic_prefix, skip, count, order):
        """
        Get the list of tags for a given category name. category can have multiple 
        tags and tags could belong to multiple categories
        :param topic_prefix: topic_prefix for which associated tags should 
        be returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        :return: list of (tag names, its data type/kind)
        :type topic_prefix: str
        :type skip: int
        :type count: int
        :type order: str
        :rtype: list
        """

        return self.query_tags_by_topic(topic_prefix, skip, count, order)

    @abstractmethod
    def query_tags_by_topic(self, topic_prefix, skip=0, count=None,
                            order=None):
        pass

    @RPC.export
    def get_topics_by_tags(self, and_condition=None, or_condition=None,
                           regex_and=None, regex_or=None, condition=None,
                           skip=0, count=None, order=None):
        """
        
        :param and_condition: dictionary of tag and its corresponding values 
        that should be matched using equality operator and combined with AND 
        condition.only topics that match all the tags in the list would be 
        returned
        :param or_condition: dictionary of tag and its corresponding values 
        that should be matched using equality operator and combined with OR 
        condition. topics that match any of the tags in the list would be 
        returned.
        :param regex_and: dictionary of tag and its corresponding values that 
        should be matched using a regular expression match and combined with 
        AND condition. only topics that match all the tags in the list would 
        be returned
        :param regex_or: dictionary of tag and its corresponding values that 
        should be matched using a regular expression match and combined with 
        OR condition. topics that match any of the tags in the list would be 
        returned.
        :param condition: conditional statement to be used for matching tags. 
        If this parameter is provided the above four parameters are ignored. 
        The value for this parameter should be an expression that contains one 
        or more query conditions combined together with an "AND" or "OR".
        Query conditions can be grouped together using parenthesis.
        Each condition in the expression should conform to one of the 
        following format:

        1. <tag name/ parent.tag_name> <binary_operator> <value>
        2. <tag name/ parent.tag_name> 
        3. <tag name/ parent.tag_name> REGEXP <regular expression within single 
           quotes
        4. the word NOT can be prefixed before any of the above three to negate
           the condition.
        5. expressions can be grouped with parenthesis. For example
        
          .. code-block:: python
        
            condition="(tag1 = 1 or tag1 = 2) and not (tag2 < '' and tag2 > '') and tag3 and tag4 REGEXP '^a.*b$'"
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        
        :type and_condition: dict
        :type or_condition: dict
        :type regex_and: dict
        :type regex_or: dict
        :type condition: str
        :type skip: int
        :type count: int
        :type order: str
        :return: list of topics/topic_prefix that match the given query 
        conditions
        :rtype: list
        """

        if and_condition or or_condition or regex_and or regex_or or condition:
            self.query_topics_by_tags(and_condition, or_condition,
                                      regex_and, regex_or, condition, skip,
                                      count, order)
        else:
            raise ValueError("Please provide a valid query criteria using "
                             "one or more of the api parameters(and_condition,"
                             " or_condition, regex_and, regex_or, condition)")


    @abstractmethod
    def query_topics_by_tags(self, and_condition=None, or_condition=None,
                             regex_and=None, regex_or=None, condition=None,
                             skip=0, count=None, order=None):
        pass

    @RPC.export
    def add_topic_tags(self, topic_prefix, tags, update_version=False):
        """
        Add tags to specific topic name or topic name prefix
        :param topic_prefix: topic name or topic name prefix
        :param tags: dictionary of tag and value in the format 
        {<valid tag>:value, <valid_tag>: value,... }
        :param update_version: True/False. Default to False. 
        If set to True and if any of the tags update an existing tag value 
        the older value would be preserved as part of tag version history
        :type topic_prefix: str
        :type tags: dict
        :type update_version: bool
        """
        self.insert_topic_tags(topic_prefix, tags, update_version)

    @abstractmethod
    def insert_topic_tags(self, topic_prefix, tags, update_version=False):
        pass


    @RPC.export
    def add_tags(self, tags, update_version=False):
        """
        Add tags to multiple topics
        :param tags: dictionary object or file containing the topic and the 
        tag details. dictionary object or the file content should be of the 
        format:

        .. code-block:: python

        <topic_name or prefix or topic_name pattern>: {<valid tag>:<value>, ... }, ... }
        
        :param update_version: True/False. Default to False. 
        If set to True and if any of the tags update an existing tag 
        value the older value would be preserved as part of tag version history
        :type tags: dict
        :type update_version: bool
        """
        self.insert_tags(tags, update_version)

    @abstractmethod
    def insert_tags(self, tags, update_version=False):
        pass






