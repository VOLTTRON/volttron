# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

import gevent
from volttron.platform.vip.agent.utils import build_agent

agent = build_agent(identity='trigger')

remote_path = "/home/osboxes/Desktop/f1.txt"
local_path = "/home/osboxes/Downloads/f1.txt"
# result = agent.vip.rpc.call("scp.agent", "trigger_download",
#                             remote_path="/home/osboxes/Downloads/f2.txt",
#                             local_path="/home/osboxes/Desktop/f6.txt").get(timeout=10)
# result = agent.vip.rpc.call("scp.agent", "trigger_upload",
#                             remote_path="/home/osboxes/Downloads/f6.txt",
#                             local_path="/home/osboxes/Desktop/f6.txt").get(timeout=10)

# print(f"The result was {result}")
agent.vip.pubsub.publish(peer='pubsub', topic="transfer", message=dict(remote_path=remote_path,
                                                                       local_path=local_path,
                                                                       direction="SENDING")).get(timeout=5)
gevent.sleep(10)
agent.vip.pubsub.publish(peer='pubsub', topic="transfer", message=dict(remote_path=remote_path,
                                                                       local_path=local_path,
                                                                       direction="RECEIVING")).get(timeout=5)
agent.core.stop()
print("Complete")

# scratch for testing.
# check_known_host = True
# compression = "yes"
# identities_only = "yes"
#
# id_file = "~/.ssh/id_rsa"
# #assert Path(id_file).expanduser().exists()
# id_file = str(Path(id_file).expanduser())
#
# user = "osboxes@localhost"
# from_file = "/home/osboxes/java_error_in_PYCHARM_2719.log"
# to_file = "/home/osboxes/Downloads/java_error_in_PYCHARM_2865.log"
#
# #which_way = WhichWayEnum.SENDING
# which_way = WhichWayEnum.RECEIVING
#
# cmd = ["scp", "-o", "LogLevel=VERBOSE", "-o", "PasswordAuthentication=no", "-o", "IdentitiesOnly=yes"] # , "-o", "LogLevel", "VERBOSE"]
# if which_way == WhichWayEnum.SENDING:
#     cmd.extend([from_file, f"{user}:{to_file}"])
# else:
#     cmd.extend([f"{user}:{from_file}", f"{to_file}"])
#
# # results = subprocess.Popen(cmd,
# #                            stderr=subprocess.PIPE, stdout=subprocess.PIPE)
# #
# # print(f"ERROR: {results.stderr.read().decode('utf-8')}")
# # print(f"OUT: {results.stdout.read().decode('utf-8')}")
# results = execute_command(cmd)
#
# print(results)
