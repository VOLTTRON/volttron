# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met: 
# 
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution. 
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
# 
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# 
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

'''VOLTTRON platform™ topic matching for agent callbacks.

Declaratively attach topic prefix and additional tests for topic
matching to agent methods allowing for automated callback registration
and topic subscription.

Example:

    class MyAgent(BaseAgent):
        @match_regex('topic1/(sub|next|part)/title[1-9]')
        def on_subtopic(topic, headers, message, match):
            # This is only executed if topic matches regex
            ...

        @match_glob('root/sub/*/leaf')
        def on_leafnode(topic, headers, message, match):
            # This is only executed if topic matches glob
            ...

        @match_exact('building/xyz/unit/condenser')
        @match_start('campus/PNNL')
        @match_end('unit/blower')
        def on_multimatch(topic, headers, message, match):
            # Multiple matchers can be attached to a method
            ...
'''

import re


__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'


def iter_match_tests(obj):
    '''Iterate match tests attached to the methods of an object.

    Each iterated item is the 3-tuple (prefix, method, test) where
    prefix and test are the same as in match_test() and method is the
    method to which the test was attached (and is the expected
    callback).
    '''
    for name in dir(obj):
        try:
            method = getattr(obj, name)
            tests = method._match_topics
        except AttributeError:
            continue
        for prefix, test in tests:
            yield prefix, method, test


def match_test(prefix, test=None):
    '''Decorate a callback method with subscription and test information.

    Returns a decorator to attach (prefix, test) 2-tuples to methods
    which can be inspected to automatically subscribe to a topic prefix
    and provide a test for triggering a call back to the method.

    prefix must match the start of a desired topic and test is either
    None or a function of the form test(topic, matched) where topic is
    the full topic to test against and matched should be the same as
    prefix.  The test function must return a value that evaluates to
    True if the topic is a match or a value that evaluates to False
    otherwise.  The test function is only called if
    `topic.startswith(prefix)` is True.  If test is None, it is the same
    as if `test = lambda topic, matched: True`.
    '''
    def decorate(func):
        '''Add (prefix, test) tuple to func's match_topics list.'''
        try:
            tests = func._match_topics
        except AttributeError:
            func._match_topics = tests = set()
        tests.add((prefix, test))
        return func
    return decorate


def _regex_split(pattern):
    '''Split a regular expression into static prefix and dynamic suffix.

    Find the first variable part of a regular expression and return a
    2-tuple containing the static prefix and the remaining pattern.
    '''
    escape = False
    prefix = []
    i = 0
    for i, token in enumerate(pattern):
        if token == '\\':
            escape = not escape
            if escape:
                continue
        elif token in '.^$*+?|{}[]()':
            if not escape:
                break
            escape = False
        elif escape:
            break
        prefix.append(token)
    return ''.join(prefix), pattern[i:]


def _test_regex(pattern):
    '''Return match_test()-compatible regular expression test function.'''
    regex = re.compile(pattern)
    return lambda topic, matched: regex.match(topic[len(matched):])


def test_regex(pattern):
    '''Return the static prefix and a regex test function for pattern.'''
    prefix, pattern = _regex_split(pattern)
    return prefix, _test_regex(pattern)


def match_regex(pattern):
    '''Return a match decorator for the given regular expression.'''
    return match_test(*test_regex(pattern))


def _translate(pattern):
    '''Return a regular expression for the given glob pattern.'''
    escape = False
    result = []
    range_start = None
    i = 0
    for i, tok in enumerate(pattern):
        if escape:
            escape = False
        elif tok == '\\':
            escape = True
        elif range_start is not None:
            if tok == ']':
                range_start = None
                tok += ')'
            elif tok == '!' and i == range_start + 1:
                tok = '^'
        elif tok == '*':
            if result and result[-1] == '([^/]*)':
                result.pop()
                tok = '(.*)'
            tok = '([^/]*)'
        elif tok == '?':
            tok = '(.)'
        elif tok == '[':
            range_start = i
            result.append('(')
        else:
            tok = re.escape(tok)
        result.append(tok)
    return ''.join(result)


def _split_glob(pattern):
    '''Split a glob pattern into its static prefix and dynamic suffix.'''
    escape = False
    prefix = []
    i = 0
    for i, tok in enumerate(pattern):
        if tok == '\\':
            escape = not escape
            if escape:
                continue
        elif escape:
            escape = False
        elif tok in '*?[':
            break
        prefix.append(tok)
    return ''.join(prefix), _translate(pattern[i:])


def test_glob(pattern):
    '''Return static prefix and regex test for glob pattern.
    
    The pattern may include the following special wildcard patterns:

        *      Matches zero or more characters.
        **     Matches zero or more characters, including forward
               slashes (/).
        ?      Matches any single character
        [...]  Matches any single characters between the brackets.  A
               range of adjacent characters may be matched using a
               hyphen (-) between the start and end character.  To
               include the hyphen as a search character, include it at
               the end of the pattern.  The range may be negated by
               immediately following the opening [ with a ^ or !.
    '''
    prefix, pattern = _split_glob(pattern)
    return prefix, _test_regex(pattern)


def match_glob(pattern):
    '''Return a match decorator for the given glob pattern.'''
    return match_test(*test_glob(pattern))


def test_exact(topic, matched):
    '''Test if topic and match are exactly equal.'''
    return topic == matched


def match_exact(topic):
    '''Return a match decorator to match a topic exactly.'''
    return match_test(topic, test_exact)


def match_start(prefix):
    '''Return a match decorator to match the start of a topic.'''
    return match_test(prefix)


def test_end(suffix):
    '''Return a test function to match the end of a topic.'''
    return lambda topic, matched: topic.endswith(suffix)


def match_end(suffix, prefix=''):
    '''Return a match decorator to match the end of a topic.'''
    return match_test(prefix, test_endswith(suffix))


def test_contains(substring):
    '''Return a test function to match a topic containing substring.'''
    return lambda topic, matched: substring in topic


def match_contains(substring, prefix=''):
    '''Return a match decorator to match a component of a topic.'''
    return match_test(prefix, test_contains(substring))


def test_subtopic(subtopic, max_levels=None):
    '''Return a test function to match a topic component after the prefix.'''
    return (lambda topic, matched: subtopic in
                       topic.split('/')[len(matched.split('/')):][:max_levels])

def match_subtopic(prefix, subtopic, max_levels=None):
    '''Return a match decorator to match a subtopic.'''
    return match_test(prefix, test_subtopic(subtopic, max_levels))


def match_all(func):
    '''Wildcard matcher to register callback for every message.'''
    return match_test('')(func)


def match_headers(required_headers):
    '''Only call function if required headers match.

    match_headers takes a single argument, required_headers, that is a
    dictionary containing the required headers and values that must
    match for the wrapped handler function to be called.

    This decorator is not very useful on its own, because it doesn't
    trigger any subscriptions, but can be useful to filter out messages
    that don't contain the required headers and values.
    '''
    def decorator(func):
        def wrapper(self, topic, headers, message, match):
            for key, required_value in required_headers.iteritems():
                try:
                    value = headers[key]
                except KeyError:
                    return
                if value != required_value:
                    return
            return func(self, topic, headers, message, match)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__dict__.update(func.__dict__)
        return wrapper
    return decorator

