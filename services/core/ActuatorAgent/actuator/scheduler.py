# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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


import bisect
import logging
from pickle import dumps, loads
from collections import defaultdict, namedtuple
from copy import deepcopy
from datetime import timedelta

from volttron.platform.agent import utils

PRIORITY_HIGH = 'HIGH'
PRIORITY_LOW = 'LOW'
PRIORITY_LOW_PREEMPT = 'LOW_PREEMPT'
ALL_PRIORITIES = {PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_LOW_PREEMPT}

# RequestResult - Result of a schedule request returned from the schedule
# manager.
RequestResult = namedtuple('RequestResult', ['success', 'data', 'info_string'])
DeviceState = namedtuple('DeviceState',
                         ['agent_id', 'task_id', 'time_remaining'])
_log = logging.getLogger(__name__)


class TimeSlice(object):
    def __init__(self, start=None, end=None):
        if end is None:
            end = start
        if start is not None:
            if end < start:
                raise ValueError('Invalid start and end values.')
        self._start = start
        self._end = end

    def __repr__(self):
        return 'TimeSlice({start!r},{end!r})'.format(start=self._start,
                                                     end=self._end)

    def __str__(self):
        return '({start} <-> {end})'.format(start=self._start, end=self._end)

    @property
    def end(self):
        return self._end

    @property
    def start(self):
        return self._start

    def __cmp__(self, other):
        if self._start >= other._end:
            return 1
        if self._end <= other._start:
            return -1
        return 0

    # def __ne__(self, other):
    #     return self.__cmp__(other) != 0
    #
    # def __gt__(self, other):
    #     return self.__cmp__(other) > 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    # def __ge__(self, other):
    #     return self.__cmp__(other) >= 0
    #
    # def __le__(self, other):
    #     return self.__cmp__(other) <= 0

    def __contains__(self, other):
        return self._start < other < self._end

    def stretch_to_include(self, time_slice):
        if self._start is None or time_slice._start < self._start:
            self._start = time_slice._start
        if self._end is None or time_slice._end > self._end:
            self._end = time_slice._end

    def contains_include_start(self, other):
        """Similar to == or "in" but includes time == self.start"""
        return other in self or other == self.start


class Task(object):
    STATE_PRE_RUN = 'PRE_RUN'
    STATE_RUNNING = 'RUNNING'
    STATE_PREEMPTED = 'PREEMPTED'
    STATE_FINISHED = 'FINISHED'

    def __init__(self, agent_id, priority, requests):
        self.agent_id = agent_id
        self.priority = priority
        self.time_slice = TimeSlice()
        self.devices = defaultdict(Schedule)
        self.state = Task.STATE_PRE_RUN

        self.populate_schedule(requests)

    def change_state(self, new_state):
        if self.state == new_state:
            return

        # TODO: We can put code here for managing state changes.

        self.state = new_state

    def populate_schedule(self, requests):
        for request in requests:
            device, start, end = request

            time_slice = TimeSlice(start, end)
            if not isinstance(device, str):
                raise ValueError('Device not string.')
            self.devices[device].schedule_slot(time_slice)
            self.time_slice.stretch_to_include(time_slice)

    def make_current(self, now):
        if self.state == Task.STATE_FINISHED:
            self.devices.clear()
            return

        for device, schedule in list(self.devices.items()):
            if schedule.finished(now):
                del self.devices[device]

        if self.time_slice.contains_include_start(now):
            if self.state != Task.STATE_PREEMPTED:
                self.change_state(Task.STATE_RUNNING)

        elif self.time_slice > TimeSlice(now):
            self.change_state(Task.STATE_PRE_RUN)

        elif self.time_slice < TimeSlice(now):
            self.change_state(Task.STATE_FINISHED)

    def get_current_slots(self, now):
        result = {}
        for device, schedule in self.devices.items():
            time_slot = schedule.get_current_slot(now)
            if time_slot is not None:
                result[device] = time_slot

        return result

    def get_conflicts(self, other):
        results = []
        for device, schedule in self.devices.items():
            if device in other.devices:
                conflicts = other.devices[device].get_conflicts(schedule)
                results.extend(
                    [device, str(x.start), str(x.end)] for x in conflicts)

        return results

    def check_can_preempt_other(self, other):
        if self.priority != PRIORITY_HIGH:
            return False

        if other.priority == PRIORITY_HIGH:
            return False

        if other.state == Task.STATE_RUNNING and other.priority != \
                PRIORITY_LOW_PREEMPT:
            return False

        return True

    def preempt(self, grace_time, now):
        """Return true if there are time slots that have a grace period left"""
        self.make_current(now)
        if self.state == Task.STATE_PREEMPTED:
            return True
        if self.state == Task.STATE_FINISHED:
            return False

        current_time_slots = []
        for schedule in self.devices.values():
            current_time_slots.extend(
                schedule.prune_to_current(grace_time, now))

        self.change_state(
            Task.STATE_FINISHED if not current_time_slots else
            Task.STATE_PREEMPTED)

        if self.state == Task.STATE_PREEMPTED:
            self.time_slice = TimeSlice(now, now + grace_time)
            return True

        return False

    def get_next_event_time(self, now):
        device_schedules = (x.get_next_event_time(now) for x in
                            self.devices.values())
        events = [x for x in device_schedules if x is not None]

        if events:
            return min(events)

        return None


class ScheduleError(Exception):
    pass


class Schedule(object):
    def __init__(self):
        self.time_slots = []

    def check_availability(self, time_slot):
        start_slice = bisect.bisect_left(self.time_slots, time_slot)
        end_slice = bisect.bisect_right(self.time_slots, time_slot)
        return set(self.time_slots[start_slice:end_slice])

    def make_current(self, now):
        """Should be called before working with a schedule.
        Updates the state to the schedule to eliminate stuff in the past."""
        now_slice = bisect.bisect_left(self.time_slots, TimeSlice(now))
        _log.debug("now_slice in make_current {}".format(now_slice))
        if now_slice > 0:
            del self.time_slots[:now_slice]

    def schedule_slot(self, time_slot):
        if self.check_availability(time_slot):
            raise ScheduleError('DERP! We messed up the scheduling!')

        bisect.insort(self.time_slots, time_slot)

    def get_next_event_time(self, now):
        """Run this to know when to the next state change is going to happen
        with this schedule"""
        self.make_current(now)
        if not self.time_slots:
            return None
        _log.debug("in schedule get_next_event_time timeslots {} now {}"
                   .format(self.time_slots[0], now))
        next_time = self.time_slots[0].end if self.time_slots[
            0].contains_include_start(now) else self.time_slots[0].start
        # Round to the next second to fix timer goofyness in agent timers.
        if next_time.microsecond:
            next_time = next_time.replace(microsecond=0) + timedelta(seconds=1)

        return next_time

    def get_current_slot(self, now):
        self.make_current(now)
        if not self.time_slots:
            return None

        if self.time_slots[0].contains_include_start(now):
            return self.time_slots[0]

        return None

    def prune_to_current(self, grace_time, now):
        """Use this to prune a schedule due to preemption."""
        current_slot = self.get_current_slot(now)
        if current_slot is not None:
            latest_end = now + grace_time
            if current_slot.end > latest_end:
                current_slot = TimeSlice(current_slot.start, latest_end)
            self.time_slots = [current_slot]
        else:
            self.time_slots = []

        return self.time_slots

    def get_conflicts(self, other):
        """Returns a list of our time_slices that conflict with the other
        schedule"""
        return [x for x in self.time_slots if other.check_availability(x)]

    def finished(self, now):
        self.make_current(now)
        return not bool(self.time_slots)

    def get_schedule(self):
        return deepcopy(self.time_slots)

    def __len__(self):
        return len(self.time_slots)

    def __repr__(self):
        pass


class ScheduleManager(object):
    def __init__(self, grace_time, now=None, save_state_callback=None, initial_state_string=None):
        self.tasks = {}
        self.running_tasks = set()
        self.preempted_tasks = set()
        self.set_grace_period(grace_time)
        self.save_state_callback = save_state_callback
        if now is None:
            now = utils.get_aware_utc_now()
        self.load_state(now, initial_state_string)

    def set_grace_period(self, seconds):
        self.grace_time = timedelta(seconds=seconds)

    def load_state(self, now, initial_state_string):
        if initial_state_string is None:
            return

        try:
            self.tasks = loads(initial_state_string)
            self._cleanup(now)
        except Exception:
            self.tasks = {}
            _log.error ('Scheduler state file corrupted!')

    def save_state(self, now):
        if self.save_state_callback is None:
            return

        try:
            self._cleanup(now)
            self.save_state_callback(dumps(self.tasks))
        except Exception:
            _log.error('Failed to save scheduler state!')

    def request_slots(self, agent_id, id_, requests, priority, now=None):
        if now is None:
            now = utils.get_aware_utc_now()
        self._cleanup(now)

        if id_ in self.tasks:
            return RequestResult(False, {}, 'TASK_ID_ALREADY_EXISTS')

        if id_ is None:
            return RequestResult(False, {}, 'MISSING_TASK_ID')

        if priority is None:
            return RequestResult(False, {}, 'MISSING_PRIORITY')
        if priority not in ALL_PRIORITIES:
            return RequestResult(False, {}, 'INVALID_PRIORITY')

        if agent_id is None:
            return RequestResult(False, {}, 'MISSING_AGENT_ID')

        if requests is None or not requests:
            return RequestResult(False, {}, 'MALFORMED_REQUEST_EMPTY')
        if not isinstance(agent_id, str) or not agent_id:
            return RequestResult(False, {},
                                 'MALFORMED_REQUEST: TypeError: agentid must '
                                 'be a nonempty string')
        if not isinstance(id_, str) or not id_:
            return RequestResult(False, {},
                                 'MALFORMED_REQUEST: TypeError: taskid must '
                                 'be a nonempty string')

        try:
            new_task = Task(agent_id, priority, requests)
        except ScheduleError:
            return RequestResult(False, {}, 'REQUEST_CONFLICTS_WITH_SELF')
        except Exception as ex:
            return RequestResult(False, {},
                                 'MALFORMED_REQUEST: ' +
                                 ex.__class__.__name__ + ': ' + str(
                                     ex))

        conflicts = defaultdict(dict)
        preempted_tasks = set()

        for task_id, task in self.tasks.items():
            conflict_list = new_task.get_conflicts(task)
            agent_id = task.agent_id
            if conflict_list:
                if not new_task.check_can_preempt_other(task):
                    conflicts[agent_id][task_id] = conflict_list
                else:
                    preempted_tasks.add((agent_id, task_id))

        if conflicts:
            return RequestResult(False, conflicts,
                                 'CONFLICTS_WITH_EXISTING_SCHEDULES')

            # By this point we know that any remaining conflicts can be
            # preempted
        # and the request will succeed.
        self.tasks[id_] = new_task

        for _, task_id in preempted_tasks:
            task = self.tasks[task_id]
            task.preempt(self.grace_time, now)

        self.save_state(now)

        return RequestResult(True, preempted_tasks, '')

    def cancel_task(self, agent_id, task_id, now):
        if task_id not in self.tasks:
            return RequestResult(False, {}, 'TASK_ID_DOES_NOT_EXIST')

        task = self.tasks[task_id]

        if task.agent_id != agent_id:
            return RequestResult(False, {}, 'AGENT_ID_TASK_ID_MISMATCH')

        del self.tasks[task_id]

        self.save_state(now)

        return RequestResult(True, {}, '')

    def get_schedule_state(self, now):
        self._cleanup(now)
        running_results = {}
        preempted_results = {}
        for task_id in self.running_tasks:
            task = self.tasks[task_id]
            agent_id = task.agent_id
            current_task_slots = task.get_current_slots(now)
            _log.debug("current_task_slots {}".format(current_task_slots))
            for device, time_slot in current_task_slots.items():
                assert (device not in running_results)
                running_results[device] = DeviceState(agent_id, task_id, (
                    time_slot.end - now).total_seconds())

        for task_id in self.preempted_tasks:
            task = self.tasks[task_id]
            agent_id = task.agent_id
            current_task_slots = task.get_current_slots(now)
            for device, time_slot in current_task_slots.items():
                assert (device not in preempted_results)
                preempted_results[device] = DeviceState(agent_id, task_id, (
                    time_slot.end - now).total_seconds())

        running_results.update(preempted_results)
        return running_results

    def get_next_event_time(self, now):
        task_times = (x.get_next_event_time(now) for x in self.tasks.values())
        events = [x for x in task_times if x is not None]

        if events:
            return min(events)

        return None

    def _cleanup(self, now):
        """Cleans up self and contained tasks to reflect the current time.
        Should be called:
        1. Before serializing to disk.
        2. After reading from disk.
        3. Before handling a schedule submission request.
        4. After handling a schedule submission request.
        5. Before handling a state request."""

        # Reset the running tasks.
        self.running_tasks = set()
        self.preempted_tasks = set()

        for task_id in list(self.tasks.keys()):
            task = self.tasks[task_id]
            task.make_current(now)
            if task.state == Task.STATE_FINISHED:
                del self.tasks[task_id]

            elif task.state == Task.STATE_RUNNING:
                self.running_tasks.add(task_id)

            elif task.state == Task.STATE_PREEMPTED:
                self.preempted_tasks.add(task_id)

    def __repr__(self):
        pass
