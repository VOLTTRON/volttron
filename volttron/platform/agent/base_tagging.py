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

"""
Base class for tagging service implementation. Tagging Service provides api's
for users to associate haystack based tags and values to topic names and
topic name prefixes.

Implementing classes should implement the following methods

  - :py:meth:`BaseTaggingService.setup`
  - :py:meth:`BaseTaggingService.load_valid_tags`
  - :py:meth:`BaseTaggingService.load_tag_refs`
  - :py:meth:`BaseTaggingService.query_categories`
  - :py:meth:`BaseTaggingService.query_tags_by_category`
  - :py:meth:`BaseTaggingService.query_tags_by_topic`
  - :py:meth:`BaseTaggingService.query_topics_by_tags`
  - :py:meth:`BaseTaggingService.insert_topic_tags`

On start calls the following methods

  - :py:meth:`BaseTaggingService.setup`
  - :py:meth:`BaseTaggingService.load_valid_tags`
  - :py:meth:`BaseTaggingService.load_tag_refs`

Querying for topics based on tags
---------------------------------
Base tagging service provides a parser to parse query
condition for querying topics based on tags. Please see documentation of
:py:meth:`BaseTaggingService.get_topics_by_tags` for syntax definition of query

"""

from __future__ import absolute_import, print_function

import logging
import os
import re

from abc import abstractmethod

from volttron.platform.agent.known_identities import (PLATFORM_HISTORIAN)
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.vip.agent.errors import Unreachable


_log = logging.getLogger(__name__)


class BaseTaggingService(Agent):
    """This is the base class for tagging service implementations. There can
    be different implementations based on backend/data store used to persist 
    the tag details
    """

    def __init__(self, historian_vip_identity=None, **kwargs):
        super(BaseTaggingService, self).__init__(**kwargs)
        self.valid_tags = dict()
        self.tag_refs = dict()
        self.historian_vip_identity = historian_vip_identity
        if historian_vip_identity is None:
            self.historian_vip_identity = PLATFORM_HISTORIAN
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.resource_sub_dir = os.path.join(current_dir, "../../..",
                                             "volttron_data/tagging_resources")
        if not os.path.isdir(self.resource_sub_dir):
            raise ValueError("Unable to access resources directory: " +
                             self.resource_sub_dir)

        _log.debug("Done init of base tagging service")

    @Core.receiver("onstart")
    def on_start(self, sender, **kwargs):
        """
        Called on start of agent. Calls the methods

        - :py:meth:`BaseTaggingService.setup`
        - :py:meth:`BaseTaggingService.load_valid_tags`
        - :py:meth:`BaseTaggingService.load_tag_refs`

        """
        # load resources and make it available for implementing classes
        # Implementing classes can load this and/or other (additional) files
        #  as they see fit.


        os.path.realpath(__file__)

        self.setup()
        self.load_valid_tags()
        self.load_tag_refs()

    @abstractmethod
    def setup(self):
        """
        Called on start of agent
        Method to establish database connection, do any initial 
        bootstrap necessary. Example - load master list of tags, units,
        categories etc. into data store/memory
        """
        pass

    @abstractmethod
    def load_valid_tags(self):
        """
        Called right after setup to load a dictionary of valid tags. It
        should load self.valid_tags with tag and type information
        """
        pass

    @abstractmethod
    def load_tag_refs(self):
        """
        Called right after setup to load a dictionary of reference tags and
        its corresponding parent tag. Implementing methods should load
        self.tag_refs with tag and parent tag information
        """
        pass

    @RPC.export
    def get_categories(self, include_description=False, skip=0, count=None,
                       order="FIRST_TO_LAST"):
        """
        Get the available list tag categories. category can have multiple tags
        and tags could belong to multiple categories

        :param include_description: indicate if result should include
         available description for categories returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or "LAST_TO_FIRST"
        :type include_description: bool
        :type skip: int
        :type count: int
        :type order: str
        :return: list of category names if include_description is False,
         list of (category name, description) if include_description is True
        :rtype: list
        """

        _log.debug("query params: skip:{} count:{} order:{}".format(skip,
                                                                    count,
                                                                    order))
        return self.query_categories(include_description, skip, count, order)

    @abstractmethod
    def query_categories(self, include_description=False, skip=0, count=None,
                         order="FIRST_TO_LAST"):
        """

        Get the available list tag categories. category can have
        multiple tags and tags could belong to multiple categories

        :param include_description: indicate if result should include
         available description for categories returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or "LAST_TO_FIRST"
        :type include_description: bool
        :type skip: int
        :type count: int
        :type order: str
        :return: list of category names if include_description is False,
         list of (category name, description) if include_description is True
        :rtype: list
        """

        pass

    @RPC.export
    def get_tags_by_category(self, category, include_kind=False,
                             include_description=False, skip=0, count=None,
                             order="FIRST_TO_LAST"):
        """
        Get the list of tags for a given category name. category can have 
        multiple tags and tags could belong to multiple categories
        
        :param category: name of the category for which associated tags 
         should be returned
        :param include_kind: indicate if result should include the 
         kind/datatype for tags returned
        :param include_description: indicate if result should include 
         available description for tags returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or "LAST_TO_FIRST"
        :return: Will return one of the following
        
          - list of tag names  
          - list of (tags, its data type/kind) if include_kind is True 
          - list of (tags, description) if include_description is True
          - list of (tags, its data type/kind, description) if include_kind
            is True and include_description is true
          
        :type category: str
        :type include_kind: bool
        :type include_description: bool
        :type skip: int
        :type count: int
        :type order: str
        :rtype: list
        """
        return self.query_tags_by_category(category, include_kind,
                                           include_description, skip, count,
                                           order)

    @abstractmethod
    def query_tags_by_category(self, category, include_kind=False,
                             include_description=False, skip=0, count=None,
                             order="FIRST_TO_LAST"):
        """
        Get the list of tags for a given category name. category can have
        multiple tags and tags could belong to multiple categories

        :param category: name of the category for which associated tags
         should be returned
        :param include_kind: indicate if result should include the
         kind/datatype for tags returned
        :param include_description: indicate if result should include
         available description for tags returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or "LAST_TO_FIRST"
        :return: Will return one of the following

          - list of tag names
          - list of (tags, its data type/kind) if include_kind is True
          - list of (tags, description) if include_description is True
          - list of (tags, its data type/kind, description) if
            include_kind is True and include_description is true

        :type category: str
        :type include_kind: bool
        :type include_description: bool
        :type skip: int
        :type count: int
        :type order: str
        :rtype: list
        """

        pass

    @RPC.export
    def get_tags_by_topic(self, topic_prefix, include_kind=False,
                             include_description=False, skip=0, count=None,
                             order="FIRST_TO_LAST"):
        """
        Get the list of tags for a given topic prefix or name.

        :param topic_prefix: topic_prefix for which associated tags should 
         be returned
        :param include_kind: indicate if result should include the 
         kind/datatype for tags returned
        :param include_description: indicate if result should include 
         available description for tags returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or  "LAST_TO_FIRST"
        :return: Will return one of the following
        
          - list of (tag name, value)
          - list of (tag name, value, data type/kind) if include_kind is True
          - list of (tag name, value, description) if include_description is True
          - list of (tags, value, data type/kind, description) if
          include_kind is True and include_description is true

        :type topic_prefix: str
        :type include_kind: bool
        :type include_description: bool
        :type skip: int
        :type count: int
        :type order: str
        :rtype: list
        """

        return self.query_tags_by_topic(topic_prefix, include_kind,
                                        include_description, skip, count,
                                        order)

    @abstractmethod
    def query_tags_by_topic(self, topic_prefix, include_kind=False,
                            include_description=False, skip=0, count=None,
                            order="FIRST_TO_LAST"):
        """
        Get the list of tags for a given topic prefix or name.

        :param topic_prefix: topic_prefix for which associated tags should
         be returned
        :param include_kind: indicate if result should include the
         kind/datatype for tags returned
        :param include_description: indicate if result should include
         available description for tags returned
        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or "LAST_TO_FIRST"
        :return: Will return one of the following

          - list of (tag name, value)
          - list of (tag name, value, data type/kind) if include_kind is True
          - list of (tag name, value, description) if
            include_description is True
          - list of (tags, value, data type/kind, description) if
            include_kind is True and include_description is true

        :type topic_prefix: str
        :type include_kind: bool
        :type include_description: bool
        :type skip: int
        :type count: int
        :type order: str
        :rtype: list
        """

        pass

    @RPC.export
    def get_topics_by_tags(self, and_condition=None, or_condition=None,
                           condition=None, skip=0, count=None, order=None):
        """
        Get list of topic names and topic name prefixes based on gives tags
        and values. This method parses the query condition creates an
        abstract syntax tree that represents the unambiguous query and calls
        method :py:meth:`BaseTaggingService.query_topics_by_tags` of the
        implementing service to further process the ast and return list of
        topic prefixes

        :param and_condition: dictionary of tag and its corresponding values
         that should be matched using equality operator or a list of tags
         that should exists/be true. Tag conditions are combined with AND
         condition. Only topics that match all the tags in the list would be
         returned
        :param or_condition: dictionary of tag and its corresponding values
         that should be matched using equality operator or a list tags that
         should exist/be true. Tag conditions are combined with OR condition.
         Topics that match any of the tags in the list would be returned.
         If both and_condition and or_condition are provided then they
         are combined using AND operator.
        :param condition: conditional statement to be used for matching tags.
         If this parameter is provided the above two parameters are ignored.
         The value for this parameter should be an expression that contains one
         or more query conditions combined together with an "AND" or "OR".
         Query conditions can be grouped together using parenthesis.
         Each condition in the expression should conform to one of the
         following format:

            1. <tag name/ parent.tag_name> <binary_operator> <value>
            2. <tag name/ parent.tag_name>
            3. <tag name/ parent.tag_name> LIKE <regular expression within
               single quotes
            4. parent tag used in query(using format parent.tag_name) should be
               of type/kind Ref. For example, campusRef.geoPostalCode = "99353"
            5. the word NOT can be prefixed before any of the above three to
               negate the condition.
            6. expressions can be grouped with parenthesis.

            Example
              .. code-block:: python

                condition="(tag1 = 1 or tag1 = 2) and (tag2 < '' and tag2 >
                '') and tag3 and  (tag4 LIKE '^a.*b$')"

                condition="NOT (tag5='US' OR tag5='UK') AND NOT tag3 AND
                NOT (tag4 LIKE 'a.*')"

                condition="campusRef.geoPostalCode='20500' and equip and boiler"

        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        
        :type and_condition: dict or list
        :type or_condition: dict or list
        :type condition: str
        :type skip: int
        :type count: int
        :type order: str
        :return: list of topics/topic_prefix that match the given query 
         conditions
        :rtype: list
        """

        if not (and_condition or or_condition or condition):
            raise ValueError("Please provide a valid query criteria using "
                             "one or more of the api parameters(and_condition,"
                             " or_condition, condition)")
        if not condition:
            if and_condition and not isinstance(and_condition, list) and \
                    not isinstance(and_condition, dict):
                raise ValueError("Invalid data type ({}) for "
                                 "param and_condition.  Expecting list or "
                                 "dict".format(type(and_condition)))

            if or_condition and not isinstance(or_condition, list) and \
                    not isinstance(or_condition, dict):
                raise ValueError("Invalid data type ({}) for "
                                 "param or_condition.  Expecting list or "
                                 "dict".format(type(or_condition)))

            condition = self._process_and_or_param(and_condition,
                                                   or_condition)

        ast = parse_query(condition, self.valid_tags, self.tag_refs)
        return self.query_topics_by_tags(ast=ast, skip=skip, count=count,
                                         order=order)

    @abstractmethod
    def query_topics_by_tags(self, ast, skip=0, count=None, order=None):
        """
        Get list of topic names and topic name prefixes based on query
        condition. Query condition is passed as an abstract syntax tree.

        :param ast: Abstract syntax tree that represents conditional statement
         to be used for matching tags. The abstract syntax tree represents
         query condition that is created using the following specification

         Query condition is a boolean expression that contains one
         or more query conditions combined together with an "AND" or "OR".
         Query conditions can be grouped together using parenthesis.
         Each condition in the expression should conform to one of the
         following format:

            1. <tag name/ parent.tag_name> <binary_operator> <value>
            2. <tag name/ parent.tag_name>
            3. <tag name/ parent.tag_name> LIKE <regular expression
               within single quotes
            4. the word NOT can be prefixed before any of the above
               three to negate the condition.
            5. expressions can be grouped with parenthesis. For example

               .. code-block:: python

                condition="(tag1 = 1 or tag1 = 2) and (tag2 < '' and tag2 >
                '') and tag3 and  (tag4 LIKE '^a.*b$')"
                condition="NOT (tag5='US' OR tag5='UK') AND NOT tag3 AND
                NOT (tag4 LIKE 'a.*')"
                condition="campusRef.geoPostalCode='20500' and equip and
                boiler"

        :param skip: number of tags to skip. usually used with order
        :param count: limit on the number of tags to return
        :param order: order of result - "FIRST_TO_LAST" or "LAST_TO_FIRST"

        :type ast: tuple
        :type skip: int
        :type count: int
        :type order: str
        :return: list of topics/topic_prefix that match the given query
         conditions
        :rtype: list
        """

        pass


    @RPC.export
    def add_topic_tags(self, topic_prefix, tags, update_version=False):
        """
        Add tags to specific topic name or topic name prefix. Calls the method
        :py:meth:`BaseTaggingService.add_tags`.

        Note: Use of this api require's a configured historian to be running.
        This can be configured using the optional historian_id
        configuration.If not configured, defaults to platform.historian. This
        api makes RPC calls to historian to get_topic_list api to
        get the list of topics. This is used to find topic/topic prefix
        matching any given input topic pattern or specific topic prefix.

        :param topic_prefix: topic name or topic name prefix
        :param tags: dictionary of tag and value in the format 
         {<valid tag>:value, <valid_tag>: value,... }
        :param update_version: True/False. Default to False. 
         If set to True and if any of the tags update an existing tag
         value the older value would be preserved as part of tag version history
        :type topic_prefix: str
        :type tags: dict
        :type update_version: bool
        """

        return self.add_tags({topic_prefix: tags})

    @RPC.export
    def add_tags(self, tags, update_version=False):
        """
        Add tags to multiple topics.
        Calls method :py:meth:`BaseTaggingService.insert_topic_tags`.
        Implementing methods could use
        :py:meth:`BaseTaggingService.get_matching_topic_prefixes` to get the
        list of topic prefix or topic names for a given topic pattern.

        :param tags: dictionary object or file containing the topic and the 
         tag details. Dictionary object or the file content should be of the
         format
         <topic_name or prefix or topic_name pattern>: {<valid tag>:<value>,
         ... }, ... }

        :param update_version: True/False. Defaults to False.
         If set to True and if any of the tags update an existing tag
         value the older value would be preserved as part of tag version
         history. Note: this feature is not implemented in the current
         version of sqlite and mongodb tagging service.
        :type tags: dict
        :type update_version: bool

        """
        _log.debug("add_tags: tags:{}".format(tags))
        return self.insert_topic_tags(tags, update_version)


    @abstractmethod
    def insert_topic_tags(self, tags, update_version=False):
        """
        Add tags to multiple topics.

        :param tags: dictionary object or file containing the topic
         and the tag details. dictionary object or the file content should be
         of the format:

         .. code-block:: python

            <topic_name or prefix or topic_name pattern>: {<valid
            tag>:<value>, ... }, ... }

        :param update_version: True/False. Default to False.
         If set to True and if any of the tags update an existing tag
         value the older value would be preserved as part of tag
         version history. Note: this feature is not implemented in the current
         version of sqlite and mongodb tagging service.
        :type tags: dict
        :type update_version: bool
        """
        pass

    def get_matching_topic_prefixes(self, topic_pattern):
        """
        Queries the configured/platform historian to get the list of topics
        that match the given topic pattern. So use of this api require's
        the configured historian (or platform.historian if specific historian id
        is not specified) to be running. This api makes RPC calls to
        platform.historian's :py:meth:`BaseHistorian.get_topic_list` to get
        the list of topics. This is used to find topic/topic prefix matching
        any given input topic pattern.

        Pattern matching done here is not true string pattern matching.
        Matches are applied to different topic_prefix.
        For example, 'campus/building1/device*' would match
        campus/building1/device1 and not campus/building1/device1/p1. Works
        only if separator is /. Else tags are always applied
        to full topic names

        :param topic_pattern: pattern to match again
        :type topic_pattern: str
        :return: list of topic prefixes.
        """
        # replace * with .* so regex would match correctly
        topic_pattern = topic_pattern.replace("*", ".*")
        topic_prefixes = set()
        try:
            _log.debug("Querying {} for matching topics for pattern "
                       "{}".format(self.historian_vip_identity, topic_pattern))
            topic_map = self.vip.rpc.call(
                self.historian_vip_identity,
                "get_topics_by_pattern",
                topic_pattern=topic_pattern).get(timeout=5)
            point_topics = topic_map.keys()
            if len(point_topics) == 1 and point_topics[0] == topic_pattern:
                # fixed string topic name
                topic_prefixes.add(topic_pattern)
            else:
                # topic name pattern
                for topic in point_topics:
                    # tag could be for a topic prefix and not the whole topic.
                    # eg. pattern could be 'campus/building1/device*'
                    # returned topic from get_matching_topics could be
                    # campus/building1/device1/p1, but we want to return
                    # campus/building1/device1
                    # Works only if separator is /. Else tags are always applied
                    # to full topic names
                    topic_parts = topic.split("/")
                    pattern_parts = topic_pattern.split("/")
                    result_prefix = '/'.join(topic_parts[:len(pattern_parts)])

                    # get topics_by_pattern will return based on re.match
                    # which is anything starting with given pattern
                    # but if the pattern is /campus1/device1 we want to
                    # match /campus1/device1 and not /campus1/device11
                    # if pattern is /campus1/device1.* then we match both
                    # device1 and device11
                    if re.match(topic_pattern+"$", result_prefix):
                        topic_prefixes.add(result_prefix)

            _log.debug("topic prefixes {}".format(topic_prefixes))
        except Unreachable:
            _log.error("add_topic_tags and add_tags "
                       "operations need plaform.historian to be running."
                       "Topics and topic patterns sent are matched against "
                       "list of valid topics queried"
                       " from {}".format(self.historian_vip_identity))
            raise

        except Exception as e:
            _log.error("Unknown exception while get list of topic prefix for "
                       "given topic/topic_pattern({}). Exception:{}".format(
                topic_pattern, e.args))
            raise
        return topic_prefixes

    @staticmethod
    def _process_and_or_param(query_and_cond, query_or_cond):
        """
        Generates query string based on list/dict objects
        :param query_and_cond: list/dict of criteria that get combined using
        AND operator
        :param query_or_cond: list/dict of criteria that get combined using
        OR operator
        :return: generated query string
        :rtype: str
        """
        and_str = None
        or_str = None

        if query_and_cond:
            and_dict = query_and_cond
            _log.debug("and_dict: {}".format(and_dict))
            if isinstance(query_and_cond, list):
                and_dict = {key: True for key in query_and_cond}
                _log.debug("and_dict after loop: {}".format(and_dict))
            and_str = BaseTaggingService._get_condition_str(and_dict, 'AND')
            _log.debug("and_str is " + and_str)

        if query_or_cond:
            or_dict = query_or_cond
            _log.debug("or_dict: {}".format(or_dict))
            if isinstance(query_or_cond, list):
                or_dict = {key: True for key in query_or_cond}
                _log.debug("or_dict: after loop:{}".format(or_dict))
            or_str = BaseTaggingService._get_condition_str(or_dict, 'OR')

        condition = None
        if and_str and or_str:
            condition = and_str + ' AND ' + or_str
        elif and_str:
            condition = and_str
        elif or_str:
            condition = or_str

        _log.debug("Query condition generated based on and and or params: "
                   "{}".format(condition))
        return condition

    @staticmethod
    def _get_condition_str(condition_dict, operator):
        """
        Build a where clause string that confirms to the same rules as
        user's specified query condition based on condition passed as
        dictionary. Uses equality operator to compare.
        :param condition_dict: dictionary of tag and values
        :param operator: operator to combine multiple tag/value pairs - AND
        or OR
        :return: where clause string
        :rtype: str
        """
        where_clause = list()
        for key in condition_dict:
            value = condition_dict[key]
            where_clause.append(str(key))
            if not isinstance(value, bool):
                if isinstance(value, str):
                    where_clause.append("=")
                    where_clause.append(repr(value))
                else:
                    where_clause.append("=")
                    where_clause.append(str(value))
            where_clause.append(operator)

        where_clause.pop(-1)
        return " ".join(where_clause)



# Ply parsing for query of the format
#
# "(tag1 = 1 or tag1 = 2) and not (tag2 < '' and tag2 > '') and tag3 and tag4 LIKE '^a.*b$'"
#
# precedence
# +
# -
# *
# /
# unary -
#
# =
# !=
# >=
# <=
# >
# <
# LIKE
#
# AND
# OR
# NOT
#
# INTEGER
# FLOATING_POINT
# STRING (single or double-quoted)


# Query parser
import ply.yacc as yacc
import ply.lex as lex

# Tokens
# ()
# uminus
# * / %
# + -
# >= <= > <
# = != not like
# and
# or

reserved = {'and': 'AND', 'or': 'OR', 'not': 'NOT', 'like': 'LIKE'}

tokens = ['ID', 'NUMBER', 'FPOINT', 'SQUOTE_STRING', 'DQUOTE_STRING','PLUS',
          'MINUS', 'TIMES', 'DIVIDE', 'MOD', 'EQ', 'GE', 'LE', 'LT', 'GT',
          'NEQ', 'LPAREN', 'RPAREN'] + list(reserved.values())
valid_tags = dict()
tag_refs = dict()

t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_MOD = r'\%'
t_EQ = r'='
t_NEQ = r'!='
t_GE = r'>='
t_LE = r'<='
t_GT = r'>'
t_LT = r'<'
t_LPAREN = r'\('
t_RPAREN = r'\)'


# ignored characters
t_ignore = ' \t'


def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*\.*[a-zA-Z_][a-zA-Z_0-9]*'
    tags = t.value.split('.')
    t.type = reserved.get(t.value.lower(), 'ID')  # Check for reserved words
    global valid_tags, tag_refs
    if valid_tags and t.type == 'ID':
        if len(tags) == 1:
            child_tag = tags[0]
        elif len(tags) == 2:
            child_tag = tags[1]
            if not tag_refs.has_key(tags[0]):
                raise ValueError("{} is not a valid reference tag. Only "
                                 "reference tags (kind/type=Ref) can be "
                                 "parent tags. Also make sure "
                                 "reference tags and its corresponding "
                                 "parent tags are loaded correctly during "
                                 "init of your tagging service"
                                 "".format(tags[0]))
        else:
            raise ValueError("Left hand side of expression can only be of "
                             "the format tag or parent_tag.tag where "
                             "parent_tag should be a valid tag with "
                             "type/kind as Ref")

        if not valid_tags.has_key(child_tag):
            raise ValueError("Invalid tag {} at line number {} and column "
                             "number {}".format(child_tag,
                                                t.lineno,
                                                t.lexpos))
    return t

# TODO - find the right regex for single or double quote string.
# r'([\'\"])([^\\\n]|(\\.))*?\1' does not work.
def t_SQUOTE_STRING(t):
    r'\'([^\\\n]|(\\.))*?\''
    return t

def t_DQUOTE_STRING(t):
    r'\"([^\\\n]|(\\.))*?\"'
    return t


def t_FPOINT(t):
    '[-+]?\d+(\.(\d+)?([eE][-+]?\d+)?|[eE][-+]?\d+)'
    try:
        t.value = float(t.value)
        pass
    except ValueError:
        raise ValueError("Floating point conversion error for %d", t.value)
    return t


def t_NUMBER(t):
    r'(-)?\d+'
    try:
        t.value = int(t.value)
        pass
    except ValueError:
        raise ValueError("Integer value too large: %d", t.value)
    return t


def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n")


def t_error(t):
    raise ValueError("Illegal character '%s'" % t.value[0])
    #t.lexer.skip(1)


# Parsing rules
# ()
# uminus
# * / %
# + -
# >= <= > <
# = != not like
# and
# or

precedence = (
    ('left', 'OR'), ('left', 'AND'), ('left', 'EQ', 'NEQ', 'NOT', 'LIKE'),
    ('left', 'GT', 'LT', 'GE', 'LE'), ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE', 'MOD'), ('right', 'UMINUS'),
    ('left', 'PAREN'),)


def p_clause(p):
    r'clause : bool_expr'
    p[0] = p[1]


def p_clause_error(p):
    r'clause : error'
    raise ValueError("Syntax error in query condition. Line number %d and "
                     "column number %d" % (p.lineno(1), p.lexpos(1)))


def p_bool_expr_id(p):
    r'bool_expr : ID'
    #p[0] = p[1]
    p[0] = ('=', p[1], True)


def p_bool_expr_eq(p):
    r'bool_expr : ID EQ expr'
    p[0] = ('=', p[1], p[3])


def p_bool_expr_neq(p):
    r'bool_expr : ID NEQ expr'
    p[0] = ('!=', p[1], p[3])


def p_bool_expr_like1(p):
    r'bool_expr : ID LIKE SQUOTE_STRING'
    p[0] = ('LIKE', p[1], p[3][1:-1])

def p_bool_expr_like2(p):
    r'bool_expr : ID LIKE DQUOTE_STRING'
    p[0] = ('LIKE', p[1], p[3][1:-1])


def p_bool_expr_gt(p):
    r'bool_expr : ID GT expr'
    p[0] = ('>', p[1], p[3])


def p_bool_expr_ge(p):
    r'bool_expr : ID GE expr'
    p[0] = ('>=', p[1], p[3])


def p_bool_expr_lt(p):
    r'bool_expr : ID LT expr'
    p[0] = ('<', p[1], p[3])


def p_bool_expr_le(p):
    r'bool_expr : ID LE expr'
    p[0] = ('<=', p[1], p[3])


def p_bool_expr_not(p):
    r'bool_expr : NOT bool_expr'
    p[0] = ('NOT', '', p[2])


def p_bool_expr_or(p):
    r'bool_expr : bool_expr OR bool_expr'
    p[0] = ('OR', p[1], p[3])


def p_bool_expr_and(p):
    r'bool_expr : bool_expr AND bool_expr'
    p[0] = ('AND', p[1], p[3])


def p_bool_expr_paren(p):
    r'bool_expr : LPAREN bool_expr RPAREN %prec PAREN'
    p[0] = p[2]


def p_expr_minus(p):
    r'expr : expr MINUS expr'
    p[0] = ('-', p[1], p[3])


def p_expr_plus(p):
    r'expr : expr PLUS expr'
    p[0] = ('+', p[1], p[3])


def p_expr_times(p):
    r'expr : expr TIMES expr'
    p[0] = ('*', p[1], p[3])


def p_expr_div(p):
    r'expr : expr DIVIDE expr'
    p[0] = ('/', p[1], p[3])


def p_expr_mod(p):
    r'expr : expr MOD expr'
    p[0] = ('%', p[1], p[3])


def p_expr_uminus(p):
    r'expr : MINUS expr %prec UMINUS'
    p[0] = ('*', '-1', p[2])


def p_expr_paren(p):
    r'expr : LPAREN expr RPAREN %prec PAREN'
    p[0] = p[2]


def p_expr_number(p):
    r'expr : NUMBER'
    p[0] = p[1]


def p_expr_fp(p):
    r'expr : FPOINT'
    p[0] = p[1]


def p_expr_single_quote_string(p):
    r'expr : SQUOTE_STRING'
    p[0] = p[1][1:-1]

def p_expr_double_quote_string(p):
    r'expr : DQUOTE_STRING'
    p[0] = p[1][1:-1]

def p_error(p):
    raise ValueError("Syntax error in query condition. Invalid token %s "
                     "at line number %d and column number %d" % (p.value,
                                                                   p.lineno,
                                                                   p.lexpos))


def pretty_print(tup):
    if tup is None:
        return tup
    if not isinstance(tup, tuple):
        return tup
    assert len(tup) == 3
    left = ""
    if isinstance(tup[1], str):
        left = tup[1]
    else:
        left = pretty_print(tup[1])
    right = ""
    if isinstance(tup[2], str):
        right = tup[2]
    else:
        right = pretty_print(tup[2])
    assert isinstance(tup[0], str)
    return "( {} {} {})".format(left, tup[0], right)


def parse_query(query, tags, refs):
    global valid_tags, tag_refs
    valid_tags = tags
    tag_refs = refs
    query_parser = yacc.yacc()
    lexer = lex.lex()
    ast = query_parser.parse(query)
    return ast


if __name__ == "__main__":
    from volttron.platform.dbutils import mongoutils
    from volttron.platform.dbutils.sqlitefuncts import  SqlLiteFuncts
    tags = {'tag1': 'str', 'tag2': 'str', 'tag3': 'str', 'campusRef': 'ref',
            'campus':'str', 'siteRef':'ref', 'site':'str'}
    tag_refs= {'siteRef': 'site', 'campusRef': 'campus'}
    query = 'tag1 OR tag2 AND (tag3 OR tag4) OR tag2 LIKE "a.*"'
    query = 'tag1 AND tag2 OR tag4'
    query = 'tag1 AND NOT (tag3>1 AND tag2>2 OR tag4<2)'
    query = 'tag1 AND NOT(tag3="value1" OR tag1>2 AND tag3 LIKE "a.*b")'
    query = 'campusRef.tag1 = 2 OR siteRef.tag2=3 AND tag3'
    query = 'NOT(campusRef.tag1 = 2 OR siteRef.tag2=3) AND tag3'
    ast = parse_query(query, tags, tag_refs)

    print("USER QUERY:\n{}".format(query))
    print("pretty print:\n{}".format(pretty_print(ast)))
    # print ("MONGO QUERY AND SUB QUERIES")
    # sub = list()
    # c = mongoutils.get_tagging_queries_from_ast(ast, tag_refs, sub)
    # print("Main query: {}".format(c))
    # print("Sub query:{}".format(sub))

    print ("SQLITE QUERY:")
    print(SqlLiteFuncts.get_tagging_query_from_ast("topic_tags", ast,
                                                   tag_refs))




