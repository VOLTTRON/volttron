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


import getpass

# Yes or no answers to questions.
y = ('Y', 'y')
n = ('N', 'n')
y_or_n = y + n


def prompt_response(prompt, valid_answers=None, default=None, echo=True,
                    mandatory=False):

    prompt += ' '
    if default is not None:
        prompt += '[{}]: '.format(default)

    if not echo:
        resp = getpass.getpass(prompt)
        return resp

    while True:
        resp = input(prompt)
        if resp == '' and default is not None:
            return default
        if str.strip(resp) == '' and mandatory:
            print('Please enter a non empty value')
            continue
        if valid_answers is None or resp in valid_answers:
            return resp
        print('Invalid response. Proper responses are:')
        print(valid_answers)
