import os
import pytest
import inspect
from volttron.platform.vip.agent import RPC
from volttron.platform.vip.agent import Agent
from typing import Optional, Union, List

class _ExporterTestAgent(Agent):
    def __init__(self, **kwargs):
        super(_ExporterTestAgent, self).__init__(**kwargs)

    @RPC.export('test_method')
    def test_method(self, param1: int, param2: Union[str, List[str]], *, param3: bool = True,
                    param4: Optional[Union[float, List[float]]] = None) -> dict:
        """Doc String"""
        return {'param1': param1, 'param2': param2, param3: param3, 'param4': param4}


@pytest.mark.rpc
def test_method_inspection(volttron_instance):
    """ Tests RPC Method Inspection

    :param volttron_instance:
    :return:
    """

    lineno = inspect.getsourcelines(_ExporterTestAgent.test_method)[1]
    test_output = {
        'doc': 'Doc String',
        'params': {'param1': {'annotation': 'int',
                              'kind': 'POSITIONAL_OR_KEYWORD'},
                   'param2': {'annotation': 'typing.Union[str, typing.List[str]]',
                              'kind': 'POSITIONAL_OR_KEYWORD'},
                   'param3': {'annotation': 'bool',
                              'default': True,
                              'kind': 'KEYWORD_ONLY'},
                   'param4': {'annotation': 'typing.Union[float, typing.List[float], '
                                            'NoneType]',
                              'default': None,
                              'kind': 'KEYWORD_ONLY'}},
        'return': 'dict',
        'source': {'file': 'volttrontesting/subsystems/test_rpc_subsystem.py',  # Must change if this file moves!
                   'line_number': lineno},
    }

    new_agent1 = volttron_instance.build_agent(identity='test_inspect1', agent_class=_ExporterTestAgent)
    new_agent2 = volttron_instance.build_agent(identity='test_inspect2')

    result = new_agent2.vip.rpc.call('test_inspect1', 'test_method.inspect').get()

    assert result == test_output
