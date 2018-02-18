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
            'filename': 'volttron.log',
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
