# Use with --log-config option:
#    volttron --log-config rotatinglog.py
import os
if 'VOLTTRON_LOG' in os.environ and os.environ['VOLTTRON_LOG']:
    volttron_log = os.environ['VOLTTRON_LOG']
else:
    volttron_log = 'volttron.log'

{
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'agent': {
            '()': 'volttron.platform.agent.utils.AgentFormatter',
        },
    },
    'handlers': {
        'rotating': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'level': 'INFO',
            'formatter': 'agent',
            'filename': volttron_log,
            'encoding': 'utf-8',
            'when': 'midnight',
            'backupCount': 7,
        },
    },
    'root': {
        'handlers': ['rotating'],
        'level': 'INFO',
    },
}
