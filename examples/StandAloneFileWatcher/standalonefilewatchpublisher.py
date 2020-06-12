'''
    This python script will listen to the specified files and publish
    updates to specific topics on the remote instance.

    Setup:
    ~~~~~

      1. Make sure volttron instance is running using tcp address. use vcfg
         command to configure the volttron instance address.

      2. Update settings.py

      3. Add this standalone agent to volttron auth entry using vctl auth add
         command. Provide ip of the volttron instance when prompted for
         address[]: and  provide public key of standalone agent when prompted
         for credentials[]:
         For more details see
         https://volttron.readthedocs.io/en/develop/devguides/walkthroughs/Agent-Authentication-Walkthrough.html

         Example command:

         .. code-block:: console

         (volttron)[vdev@cs_cbox myvolttron]$ vctl auth add
         domain []:
         address []: 127.0.0.1
         user_id []:
         capabilities (delimit multiple entries with comma) []:
         roles (delimit multiple entries with comma) []:
         groups (delimit multiple entries with comma) []:
         mechanism [CURVE]:
         credentials []: rn_V3vxTLMwaIRUEIAIHee4-qM8X70irDThcn_TX6FA
         comments []:
         enabled [True]:

      4. With a volttron activated shell this script can be run like:

         python standalonefilewatchpublisher.py

'''

from datetime import datetime
import os
import sys

import gevent
import logging


from volttron.platform.vip.agent import Agent, PubSub, RPC, Core
from volttron.platform.agent import utils
from volttron.platform.agent.utils import watch_file_with_fullpath
from volttron.platform import jsonapi


# These are the options that can be set from the settings module.
from settings import remote_url, config

# Setup logging so that we could use it if we needed to.
utils.setup_logging()
_log = logging.getLogger(__name__)

logging.basicConfig(
                level=logging.debug,
                format='%(asctime)s   %(levelname)-8s %(message)s',
                datefmt='%m-%d-%y %H:%M:%S')


class StandAloneFileWatchPublisher(Agent):
    ''' A standalone version of the FileWatcherPublisher'''
    def __init__(self, **kwargs):
        super(StandAloneFileWatchPublisher, self).__init__(**kwargs)
        self.config = config
        items = config[:]
        self.file_topic = {}
        self.file_end_position = {}
        for item in self.config:
            file = item["file"]
            self.file_topic[file] = item["topic"]
            if os.path.isfile(file):
                with open(file, 'r') as f:
                    self.file_end_position[file] = self.get_end_position(f)
            else:
                _log.error("File " + file + " does not exists. Ignoring this file.")
                items.remove(item)
        self.config = items
    
    def onmessage(self, peer, sender, bus, topic, headers, message):
        '''Handle incoming messages on the bus.'''
        d = {'topic': topic, 'headers': headers, 'message': message}
        sys.stdout.write(jsonapi.dumps(d)+'\n')

    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        _log.info("Starting "+self.__class__.__name__+" agent")
        if len(self.config) == 0 :
            _log.error("No file to watch and publish. Stopping "+self.__class__.__name__+" agent.")
            gevent.spawn_later(3, self.core.stop)
        else:
            for item in self.config:
                file = item["file"]
                self.core.spawn(watch_file_with_fullpath, file, self.read_file)

    def read_file(self, file):
        _log.debug('loading file %s', file)
        with open(file, 'r') as f:
            f.seek(self.file_end_position[file])
            for line in f:
                self.publish_file(line.strip(),self.file_topic[file])
            self.file_end_position[file] = self.get_end_position(f)

    def publish_file(self, line, topic):
        message = {'timestamp':  datetime.utcnow().isoformat() + 'Z',
                   'line': line}
        _log.debug('publishing message {} on topic {}'.format(message, topic))
        self.vip.pubsub.publish(peer="pubsub", topic=topic,
                                message=message)

    def get_end_position(self, f):
        f.seek(0, 2)
        return f.tell()


if __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)
        
        print(remote_url())
        agent = StandAloneFileWatchPublisher(address=remote_url(),
                                   identity='standalone.filewatchpublisher')
        task = gevent.spawn(agent.core.run)
        try:
            task.join()
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass
