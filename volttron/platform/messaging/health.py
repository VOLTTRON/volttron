from zmq.utils import jsonapi
from volttron.platform.agent.utils import (get_aware_utc_now,
                                           format_timestamp,
                                           parse_timestamp_string)

CURRENT_STATUS = "current_status"
LAST_UPDATED = "utc_last_updated"
CONTEXT = "context"

STATUS_GOOD = "GOOD"
STATUS_BAD = "BAD"
STATUS_UNKNOWN = "UNKNOWN"

GOOD_STATUS = STATUS_GOOD
BAD_STATUS = STATUS_BAD
UNKNOWN_STATUS = STATUS_UNKNOWN

ACCEPTABLE_STATUS = (GOOD_STATUS, BAD_STATUS, UNKNOWN_STATUS)


class Status(object):

    def __init__(self):
        self._status = GOOD_STATUS
        self._context = None
        self._last_updated = format_timestamp(get_aware_utc_now())
        self._status_changed_callback = None

    @property
    def status(self):
        return self._status

    @property
    def context(self):
        if self._context:
            if isinstance(self._context, basestring):
                return self._context
            return self._context.copy()
        return None

    @property
    def last_updated(self):
        return self._last_updated

    def update_status(self, status, context=None):
        if status not in ACCEPTABLE_STATUS:
            raise ValueError('Invalid status value {}'.format(status))
        try:
            jsonapi.dumps(context)
        except TypeError:
            raise ValueError('Context must be JSON serializable.')

        status_changed = status != self._status
        self._status = status
        self._context = context
        self._last_updated = format_timestamp(get_aware_utc_now())
        if status_changed and self._status_changed_callback:
            print(self._status_changed_callback())

    def to_json(self):
        cp = self.__dict__.copy()
        try:
            del cp['_status_changed_callback']
        except KeyError:
            pass
        return jsonapi.dumps(cp)

    @staticmethod
    def from_json(data, status_changed_callback=None):
        statusobj = Status()
        statusobj.__dict__ = jsonapi.loads(data)
        statusobj._status_changed_callback = status_changed_callback
        return statusobj

    @staticmethod
    def build(status, context=None, status_changed_callback=None):
        statusobj = Status()
        statusobj.update_status(status, context)
        statusobj._status_changed_callback = status_changed_callback
        return statusobj

