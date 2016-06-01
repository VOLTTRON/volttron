
import inspect
import logging
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

def get_table_def(config):
    default_table_def = {"table_prefix": "",
                         "data_table": "data",
                         "topics_table": "topics",
                         "meta_table": "meta"}
    tables_def = config.get('tables_def', default_table_def)
    if tables_def['table_prefix']:
        tables_def['data_table'] = tables_def['table_prefix'] + \
                                   "_" + tables_def['data_table']
        tables_def['topics_table'] = tables_def['table_prefix'] + \
                                     "_" + tables_def['topics_table']
        tables_def['meta_table'] = tables_def['table_prefix'] + \
                                   "_" + tables_def['meta_table']
    tables_def.pop('table_prefix', None)
    return tables_def

def getDBFuncts(database_type):
    mod_name = database_type + "functs"
    mod_name_path = "volttron.platform.agent.dbutils.{}".format(
        mod_name)
    loaded_mod = __import__(mod_name_path, fromlist=[mod_name])
    for name, cls in inspect.getmembers(loaded_mod):
        # assume class is not the root dbdriver
        if inspect.isclass(cls) and name != 'DbDriver':
            DbFuncts = cls
            break
    try:
        _log.debug('Historian using module: ' + DbFuncts.__name__)
    except NameError:
        functerror = 'Invalid module named ' + mod_name_path + "."
        raise Exception(functerror)
    return DbFuncts

def format_agg_time(time_period):
    return time_period