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

"""
Utility script to freeze versions in requirements.py before release. This will modify the requirements.py. It will
create a backup of the develop version as requirements_develop.py The modified requirements.py file needs to go ONLY
 into the release branch. Once release is done develop's requirements.py should be restored from requiremens_develop.py
"""
import subprocess
import os
import pprint


def main():

    # First find the pip packages in the current env
    process = subprocess.Popen(["pip", "list", "-l", "--format=freeze"], stderr=subprocess.PIPE,  stdout=subprocess.PIPE)
    (output, error) = process.communicate()
    if process.returncode != 0:
        print("Unable to get list of pip packages.")
        print(error)
        exit(1)


    versioned_list = output.decode("utf-8").splitlines()
    replacement_map = dict()
    for p in versioned_list:
        replacement_map[p.split("==")[0]] = p

    new_contents = []
    requirements_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    requirements_file_path = os.path.join(requirements_dir, "requirements.py")
    with open(requirements_file_path, "r") as f:
        for l in f:
            if l.startswith("#"):
                new_contents.append(l)
            else:
                break
    comments = "".join(new_contents)

    import requirements
    new_contents = dict()
    for var in dir(requirements):
        if not var.startswith("__"):
            value = getattr(requirements, var)
            if isinstance(value, dict) or isinstance(value, list):
                new_contents[var] = freeze_version(replacement_map, value)

    os.rename(requirements_file_path, os.path.join(requirements_dir, "requirements_develop.py"))

    pp = pprint.PrettyPrinter(indent=4, stream=f)
    with open(requirements_file_path, "w") as f:
        f.write(comments)
        f.write("\n")
        f.write("\n")
        for k, v in new_contents.items():
            f.write(f"{k} = ")
            temp_str = pp.pformat(v)
            f.write(temp_str)
            f.write("\n")
            f.write("\n")
        f.write("\n")

def freeze_version(replacement_map, value):

    if isinstance(value, list):
        new_var = list()
        for item in value:
            if isinstance(item, str):
                if not "==" in item and item in replacement_map:
                    new_var.append(replacement_map[item])
                else:
                    new_var.append(item)
            if isinstance(item, tuple):
                temp_list = []
                temp_list.append(replacement_map.get(item[0], item[0]))
                temp_list.extend(item[1:])
                new_var.append(tuple(temp_list))
    elif isinstance(value, dict):
        new_var = dict()
        for k, v in value.items():
            new_var[k] = freeze_version(replacement_map, v)
    return new_var


if __name__ == "__main__":
    main()

