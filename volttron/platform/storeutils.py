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


from string import whitespace

store_ext = ".store"
link_prefix = "config://"

def strip_config_name(config_name):
    return config_name.strip(whitespace + r'\/')

def check_for_config_link(value):
    if value.startswith(link_prefix):
        config_name = value.replace(link_prefix, '', 1)
        config_name = strip_config_name(config_name)
        return config_name.lower()
    return None

def list_unique_links(config):
    """Returns a set of config files referenced in this configuration"""
    results = set()
    if isinstance(config, dict):
        values = list(config.values())
    elif isinstance(config, list):
        values = config
    else:
        #Raw config has no links
        return results


    for value in values:
        if isinstance(value, (dict,list)):
            results.update(list_unique_links(value))
        elif isinstance(value, str):
            value = value.lower()
            if value.startswith(link_prefix):
                config_name = value.replace(link_prefix, '', 1)
                config_name = strip_config_name(config_name)
                results.add(config_name)

    return results


def check_for_recursion(new_config_name, new_config, existing_configs):
    return _follow_links(set(), new_config_name.lower(), new_config_name.lower(), new_config, existing_configs)

def _follow_links(seen, new_config_name, current_config_name, current_config, existing_configs):
    children = list_unique_links(current_config)

    if new_config_name in children:
        return True

    seen.add(current_config_name)

    for child_config_name in children - seen:
        child_config = existing_configs.get(child_config_name)
        if child_config is None:
            #Link to a non-existing config, skip in the future.
            seen.add(child_config_name)
            continue
        if _follow_links(seen, new_config_name, child_config_name, child_config, existing_configs):
            return True

    return False
