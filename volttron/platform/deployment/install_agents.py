import argparse
import hashlib
import logging
import sys
import traceback
import uuid

import gevent

from volttron.platform import config

_log = logging.getLogger(__name__)

_stdout = sys.stdout
_stderr = sys.stderr


def install_agent(opts, publickey=None, secretkey=None, callback=None):
    aip = opts.aip
    filename = opts.path
    tag = opts.tag
    vip_identity = opts.vip_identity
    if opts.vip_address.startswith('ipc://'):
        _log.info("Installing wheel locally without channel subsystem")
        filename = config.expandall(filename)
        agent_uuid = opts.connection.call('install_agent_local',
                                          filename,
                                          vip_identity=vip_identity,
                                          publickey=publickey,
                                          secretkey=secretkey)

        if tag:
            opts.connection.call('tag_agent', agent_uuid, tag)

    else:
        try:
            _log.debug('Creating channel for sending the agent.')
            channel_name = str(uuid.uuid4())
            channel = opts.connection.server.vip.channel('control',
                                                         channel_name)
            _log.debug('calling control install agent.')
            agent_uuid = opts.connection.call_no_get('install_agent',
                                                     filename,
                                                     channel_name,
                                                     vip_identity=vip_identity,
                                                     publickey=publickey,
                                                     secretkey=secretkey)

            _log.debug('Sending wheel to control')
            sha512 = hashlib.sha512()
            with open(filename, 'rb') as wheel_file_data:
                while True:
                    # get a request
                    with gevent.Timeout(60):
                        request, file_offset, chunk_size = channel.recv_multipart()
                    if request == b'checksum':
                        channel.send(sha512.digest())
                        break

                    assert request == b'fetch'

                    # send a chunk of the file
                    file_offset = int(file_offset)
                    chunk_size = int(chunk_size)
                    wheel_file_data.seek(file_offset)
                    data = wheel_file_data.read(chunk_size)
                    sha512.update(data)
                    channel.send(data)

            agent_uuid = agent_uuid.get(timeout=10)

        except Exception as exc:
            if opts.debug:
                traceback.print_exc()
            _stderr.write(
                '{}: error: {}: {}\n'.format(opts.command, exc, filename))
            return 10
        else:
            if tag:
                opts.connection.call('tag_agent',
                                     agent_uuid,
                                     tag)
        finally:
            _log.debug('closing channel')
            channel.close(linger=0)
            del channel

    name = opts.connection.call('agent_name', agent_uuid)
    _stdout.write('Installed {} as {} {}\n'.format(filename, agent_uuid, name))

    # Need to use a callback here rather than a return value.  I am not 100%
    # sure why this is the reason for allowing our tests to pass.
    if callback:
        callback(agent_uuid)


def add_install_agent_parser(add_parser_fn, has_restricted):
    install = add_parser_fn('install', help='install agent from wheel',
                            epilog='Optionally you may specify the --tag argument to tag the '
                                   'agent during install without requiring a separate call to '
                                   'the tag command. ')
    install.add_argument('path', help='path to agent wheel or directory for agent installation')
    install.add_argument('--tag', help='tag for the installed agent')
    install.add_argument('--vip-identity', help='VIP IDENTITY for the installed agent. '
                                                'Overrides any previously configured VIP IDENTITY.')

    if has_restricted:
        install.add_argument('--verify', action='store_true',
                             dest='verify_agents',
                             help='verify agent integrity during install')
        install.add_argument('--no-verify', action='store_false',
                             dest='verify_agents',
                             help=argparse.SUPPRESS)
    install.set_defaults(func=install_agent, verify_agents=True)
