__import__('warnings').warn(
    'Module {} is deprecated in favor of volttron.platform.scheduling '
    'and will be removed in a future version.'.format( __name__),
    DeprecationWarning)
from volttron.platform.scheduling import cron as schedule, parse_cron_string