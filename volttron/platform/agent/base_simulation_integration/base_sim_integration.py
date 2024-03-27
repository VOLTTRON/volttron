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


class BaseSimIntegration:
    def __init__(self, config):
        self.config = config

    def start_simulation(self, *args, **kwargs):
        pass

    def register_inputs(self, config=None, callback=None, **kwargs):
        pass

    def publish_to_simulation(self, topic, message, **kwargs):
        pass

    def make_time_request(self, time_request=None, **kwargs):
        pass

    def pause_simulation(self, timeout=None, **kwargs):
        pass

    def resume_simulation(self, *args, **kwargs):
        pass

    @property
    def is_sim_installed(self, *args, **kwargs):
        return True

    def stop_simulation(self, *args, **kwargs):
        pass
