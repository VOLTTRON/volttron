# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}
from __future__ import absolute_import, print_function

import logging
import sys
import sqlite3

from volttron.platform.agent import utils
from volttron.platform.agent.base_taggging import BaseTaggingService
from volttron.utils.docs import doc_inherit

__version__ = "1.0"

utils.setup_logging()
_log = logging.getLogger(__name__)


def sqltagging_agent(config_path, **kwargs):
    """
    This method is called by the :py:func:`service.tagging.main` to
    parse the passed config file or configuration dictionary object, validate
    the configuration entries, and create an instance of SQLTaggingService

    :param config_path: could be a path to a configuration file or can be a
                        dictionary object
    :param kwargs: additional keyword arguments if any
    :return: an instance of :py:class:`service.tagging.SQLTaggingService`
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    database = config_dict['connection']['params']['database']

    assert database is not None

    SQLTaggingService.__name__ = 'SQLTaggingService'
    return SQLTaggingService(config_dict, **kwargs)


class SQLTaggingService(BaseTaggingService):
    """This is a tagging service agent that writes data to a SQLite database.
    """
    def __init__(self, config, **kwargs):
        """Initialise the tagging service.

        :param config: dictionary object containing the configurations for
                       this tagging agent
        :param kwargs: additional keyword arguments. (optional identity and
                       topic_replace_list used by parent classes)
        """
        self.config = config
        self.tags_table = "tags"
        if config.get("table_prefix"):
            self.tags_table = config.get("table_prefix") + "_" \
                              + self.tags_table

        super(SQLTaggingService, self).__init__(config, **kwargs)


    @doc_inherit
    def setup(self):
        _log.debug("Setup of sqlite tagging agent")
        c = sqlite3.connect(self.config['connection']['params']['database'],
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        cursor = c.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='{}';".format(self.tags_table))
        table_name = cursor.fetchall()
        _log.debug(table_name)



    def query_tags_by_group(self, group_name, skip=0, count=None, order=None):
        pass

    def query_groups(self, skip=0, count=None, order=None):
        pass

    def query_tags_by_topic(self, topic_prefix, skip=0, count=None,
                            order=None):
        pass

    def insert_tags(self, tags, update_version=False):
        pass

    def insert_topic_tags(self, topic_prefix, tags, update_version=False):
        pass

    def query_topics_by_tags(self, and_condition=None, or_condition=None,
                             regex_and=None, regex_or=None, condition=None):
        pass

def main(argv=sys.argv):
    """ Main entry point for the agent.

    :param argv:
    :return:
    """

    try:
        utils.vip_main(sqltagging_agent, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
