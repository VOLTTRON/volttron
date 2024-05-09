# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import argparse
import os
from pathlib import Path
import shutil

import gevent

from volttron.platform.vip.agent.utils import build_agent


def run_tests(local_root="~/local_files", remote_root="~/remote_files"):
    agent = build_agent(identity='trigger')

    local_root = Path(local_root).expanduser()
    remote_root = Path(remote_root).expanduser()

    def build_remote_filename(filename):
        os.makedirs(remote_root, exist_ok=True)
        return str(Path(remote_root).joinpath(filename))

    def build_local_filename(filename):
        os.makedirs(local_root, exist_ok=True)
        return str(Path(local_root).joinpath(filename))

    def create_remote_file(filename, content):
        full_path = build_remote_filename(filename)
        with open(full_path, 'w') as fp:
            fp.write(content)
        return full_path

    def create_local_file(filename, content):
        full_path = build_local_filename(filename)
        with open(full_path, 'w') as fp:
            fp.write(content)
        return full_path

    def remove_files():
        shutil.rmtree(remote_root, ignore_errors=True)
        shutil.rmtree(local_root, ignore_errors=True)

    remove_files()

    remote_path = create_remote_file("t1.txt", "this is f1")
    local_path = build_local_filename("t1.after.transfer.txt")

    go = input(f"Test 1: rpc: trigger_download\n\tdownload remote_path: {remote_path}\n\tto local_path: {local_path} ")
    result = agent.vip.rpc.call("scp.agent", "trigger_download",
                                remote_path=remote_path,
                                local_path=local_path).get()
    print(f"The result was {result}\n")

    print(f"Creating test2 file")
    remote_path = build_remote_filename("t2.remote.transfer.txt")
    local_path = create_local_file("t2.txt", "This is test 2")
    go = input(f"Test 2: rpc: trigger_upload\n\tupload local_path: {local_path}\n\tto remote_path: {remote_path}  ")
    result = agent.vip.rpc.call("scp.agent", "trigger_upload",
                                remote_path=remote_path,
                                local_path=local_path).get()
    print(f"The result was {result}\n")

    print(f"Creating test3 file")
    remote_path = build_remote_filename("t3.sent.pubsub.txt")
    local_path = create_local_file("t3.txt", "This is test 3")

    go = input(f"Test 3: pubsub: SENDING\n\tlocal_path: {local_path}\n\tto remote_path: {remote_path}  ")

    agent.vip.pubsub.publish(peer='pubsub', topic="transfer", message=dict(remote_path=remote_path,
                                                                           local_path=local_path,
                                                                           direction="SENDING")).get()
    gevent.sleep(1)
    print(f"The result is {Path(remote_path).exists()}\n")
    print(f"Creating test4 file")
    remote_path = create_remote_file("t4.receive.pubsub.txt", "This is test 4")
    local_path = build_local_filename("t4.receive.txt")

    go = input(f"Test 4: pubsub: RECEIVING\n\tlocal_path: {local_path}\n\tfrom remote_path: {remote_path}  ")
    agent.vip.pubsub.publish(peer='pubsub', topic="transfer", message=dict(remote_path=remote_path,
                                                                           local_path=local_path,
                                                                           direction="RECEIVING")).get()
    gevent.sleep(1)
    print(f"The result is {Path(local_path).exists()}\n")
    agent.core.stop()
    print("Complete")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--local_root", help="Local path", default="~/local_root")
    parser.add_argument("-r", "--remote_root", help="Remote path", default="~/remote_root")

    args = parser.parse_args()
    run_tests(args.local_root, args.remote_root)
