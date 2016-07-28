import logging

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

ALERT_KEY = "alert_key"

_log = logging.getLogger(__name__)

class Status(object):
    """
    The `Status` objects wraps the context status and last reported into a
    small object that can be serialized and sent across the zmq message bus.

    There are two static methods for constructing `Status` objects:
      - from_json() Expects a json string as input.
      - build() Expects at least a status in the `ACCEPTABLE_STATUS` tuple.

    The build() method also takes a context and a callback function that will
    be called when the status changes.
    """
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
        """
        Updates the internal state of the `Status` object.

        This method will throw errors if the context is not serializable or
        if the status parameter is not within the ACCEPTABLE_STATUS tuple.

        :param status:
        :param context:
        :return:
        """
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

    def as_dict(self):
        """
        Returns a copy of the status object properties as a dictionary.

        @return:
        """
        cp = dict(status=self.status, context=self.context,
                  last_updated=self.last_updated)
        return cp

    def as_json(self):
        """
        Serializes the object to a json string.

        Note:
            Does not serialize the change callback function.

        :return:
        """
        return jsonapi.dumps(self.as_dict())

    @staticmethod
    def from_json(data, status_changed_callback=None):
        """
        Deserializes a `Status` object and returns it to the caller.

        :param data:
        :param status_changed_callback:
        :return:
        """
        _log.debug("from_json {}".format(data))
        statusobj = Status()
        cp = jsonapi.loads(data)
        cp['_status'] = cp['status']
        cp['_last_updated'] = cp['last_updated']
        cp['_context'] = cp['context']
        del cp['status']
        del cp['last_updated']
        del cp['context']
        statusobj.__dict__ = cp
        statusobj._status_changed_callback = status_changed_callback
        return statusobj

    @staticmethod
    def build(status, context=None, status_changed_callback=None):
        """
        Constructs a `Status` object and initializes its state using the
        passed parameters.

        :param status:
        :param context:
        :param status_changed_callback:
        :return:
        """
        statusobj = Status()
        statusobj.update_status(status, context)
        statusobj._status_changed_callback = status_changed_callback
        return statusobj

