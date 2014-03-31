# 
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution. 
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies, 
# either expressed or implied, of the FreeBSD Project.
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
#


from configobj import flatten_errors, ConfigObj, ParseError
from validate import Validator


__all__ = ['Config', 'ParseError']


class Config(ConfigObj):
    def load(self, inifile):
        self.filename = inifile
        self.reload()

    def validate(self, validator=None, *args, **kwargs):
        if validator is None:
            validator = Validator()
        return ConfigObj.validate(self, validator, *args, **kwargs)

    def iter_error_strings(self, errors):
        for section, key, error in flatten_errors(self, errors):
            if key is None:
                section, key = section[:-1], section[-1]
                error = 'missing required subsection'
            elif not error:
                error = 'missing required value'
            else:
                error = str(error)
            yield ('::'.join(section), key, error)

    def parser_load(self, parser, inifile=None, extra_config=None):
        if inifile:
            try:
                self.load(inifile)
            except IOError, e:
                parser.error(e)
            except ParseError, e:
                msg = str(e).rstrip('.')
                parser.error('config parse error: {0}: {1}'.format(msg, inifile))
        for names, value in extra_config:
            obj = self
            for name in names[:-1]:
                obj = obj.setdefault(name, {})
            obj[names[-1]] = self._handle_value(value)[0]
        errors = self.validate(preserve_errors=True)
        if errors is not True:
            parser._print_message(
                    '{0}: error: configuration error(s):\n'.format(parser.prog))
            for error in self.iter_error_strings(errors):
                parser._print_message('   {}: {}\n'.format('.'.join(error[:-1]),
                                                           error[-1]))
            parser.exit(1)

