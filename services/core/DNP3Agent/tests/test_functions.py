import pytest
try:
    import dnp3
except ImportError:
    pytest.skip("pydnp3 not found!", allow_module_level=True)

import copy

from dnp3.points import PointDefinitions
from dnp3.mesa.functions import FunctionDefinitions, FunctionDefinition, StepDefinition

from test_mesa_agent import POINT_DEFINITIONS_PATH, FUNCTION_DEFINITIONS_PATH


POINT_DEFINITIONS = PointDefinitions(point_definitions_path=POINT_DEFINITIONS_PATH)

enable_high_voltage_ride_through_mode = {
    'id': 'enable_high_voltage_ride_through_mode',
    'name': 'Enable High Volatge Ride-Through Mode',
    'ref': 'AN2018 Spec section 2.5.1 Table 33',
    'steps': [
        {
            'step_number': 1,
            'description': 'Set the Reference Voltage if it is not already set',
            'point_name': 'DECP.VRef.AO0',
            'optional': 'I',
            'fcode': ['direct_operate'],
            'response': 'DECP.VRef.AI29'
        },
        {
            'step_number': 2,
            'description': 'Set the Reference Voltage Offset if it is not already set',
            'point_name': 'DECP.VRefOfs.AO1',
            'optional': 'I',
            'fcode': ['direct_operate'],
            'response': 'DECP.VRefOfs.AI30'
        },
        {
            'step_number': 3,
            'description': 'Identify the meter used to measure the voltage. By default this is the System Meter',
            'point_name': 'DHVT.EcpRef.AO22',
            'optional': 'I',
            'fcode': ['direct_operate'],
            'response': 'DHVT.EcpRef.AI71'
        },
        {
            'step_number': 4,
            'description': 'Identify the index of the curve which specifies trip points when the voltage is high',
            'point_name': 'PTOV.BlkRef.AO23',
            'optional': 'M',
            'fcode': ['direct_operate'],
            'response': 'PTOV.BlkRef.AI73',
            'func_ref': 'curve'
        },
        {
            'step_number': 5,
            'description': 'Enable the Low/High Voltage Ride-Through Mode',
            'point_name': 'DHVT.ModEna.BO12',
            'optional': 'M',
            'fcode': ['select', 'operate'],
            'response': 'DHVT.ModEna.BI64'
        }
    ]
}

curve_selector_block = {
    'id': 'curve',
    'name': 'Curve',
    'ref': 'AN2018 Spec Curve Definition',
    'steps': [
        {
            'step_number': 1,
            'description': 'Select which curve to edit',
            'point_name': 'DGSMn.InCrv.AO244',
            'optional': 'M',
            'fcode': ['direct_operate'],
            'response': 'DGSMn.InCrv.AI328'
        },
        {
            'step_number': 2,
            'description': 'Specify the Curve Mode Type',
            'point_name': 'DGSMn.ModTyp.AO245',
            'optional': 'M',
            'fcode': ['direct_operate'],
            'response': 'DGSMn.ModTyp.AI329'
        },
        {
            'step_number': 3,
            'description': 'Specify that the Independent (X-Value) units for the curve',
            'point_name': 'FMARn.IndpUnits.AO247',
            'optional': 'M',
            'fcode': ['direct_operate'],
            'response': 'FMARn.IndpUnits.AI331'
        },
        {
            'step_number': 4,
            'description': 'Specify the Dependent (Y-Value) units for the curve',
            'point_name': 'FMARn.DepRef.AO248',
            'optional': 'M',
            'fcode': ['direct_operate'],
            'response': 'FMARn.DepRef.AI332',
            'action': 'publish'
        },
        {
            'step_number': 5,
            'description': 'Set X-Value and Y-Values pairs for the curve',
            'point_name': 'FMARn.PairArr.CrvPts.AO249',
            'optional': 'M',
            'fcode': ['direct_operate'],
            'response': 'FMARn.PairArr.CrvPts.AI333'
        },
        {
            'step_number': 6,
            'description': 'Set number of points used for the curve',
            'point_name': 'FMARn.PairArr.NumPts.AO246',
            'optional': 'M',
            'fcode': ['direct_operate'],
            'response': 'FMARn.PairArr.NumPts.AI330'
        }
    ]
}


class TestStepDefinition:
    """Regression tests for Step Definition."""

    @property
    def function_id(self):
        return 'enable_high_voltage_ride_through_mode'

    @property
    def step_number(self):
        return 1

    @property
    def step_json(self):
        """Return function enable_high_voltage_ride_through_mode step 1"""
        return copy.deepcopy(enable_high_voltage_ride_through_mode)['steps'][self.step_number-1]

    def validate_step_definition(self, step_json):
        exception = {}
        try:
            step_def = StepDefinition(POINT_DEFINITIONS, self.function_id, step_json)
            step_def.validate()
        except Exception as err:
            exception['key'] = type(err).__name__
            exception['error'] = str(err)
        return exception

    def test_valid_step_definition(self):
        exception = self.validate_step_definition(self.step_json)
        assert exception == {}

    def test_missing_step_number(self):
        """Test raising exception if step missing step_number"""
        step_json = self.step_json
        step_json.pop('step_number')
        exception = self.validate_step_definition(step_json)
        assert exception == {
            'key': 'AttributeError',
            'error': 'Missing step number in function {}'.format(self.function_id)
        }

    def test_missing_point_name(self):
        """Test raising exception if step missing point_name"""
        step_json = self.step_json
        step_json.pop('point_name')
        exception = self.validate_step_definition(step_json)
        assert exception == {
            'key': 'AttributeError',
            'error': 'Missing name in function {} step {}'.format(self.function_id, self.step_number)
        }

    def test_invalid_optionality(self):
        """Test raising exception if optional not O, M, or I"""
        step_json = self.step_json
        step_json.update({
            'optional': 'C'
        })
        exception = self.validate_step_definition(step_json)
        assert exception == {
            'key': 'AttributeError',
            'error': 'Invalid optional value in function {} step {}: C'.format(self.function_id, self.step_number)
        }

    def test_invalid_fcodes_type(self):
        """Test raising exception if fcodes is not a list"""
        step_json = self.step_json
        step_json.update({
            'fcodes': 'direct_operate'
        })
        exception = self.validate_step_definition(step_json)
        assert exception == {
            'key': 'AttributeError',
            'error': "Invalid fcodes in function {} step {}, type=<type 'str'>".format(self.function_id,
                                                                                       self.step_number)
        }

    def test_invalid_fcode_value(self):
        """Test raising exception if a str value in fcodes list is invalid"""
        step_json = self.step_json
        step_json.update({
            'fcodes': ['select_operate']
        })
        exception = self.validate_step_definition(step_json)
        assert exception == {
            'key': 'AttributeError',
            'error': 'Invalid fcode in function {} step {}, fcode=select_operate'.format(self.function_id,
                                                                                         self.step_number)
        }

    def test_invalid_optionality_for_read_fcode(self):
        """Test raising exception if optionality is not OPTIONAL when fcode is read"""
        step_json = self.step_json
        step_json.update({
            'fcodes': ['read', 'response']
        })
        exception = self.validate_step_definition(step_json)
        assert exception == {
            'key': 'AttributeError',
            'error': 'Invalid optionality in function {} step {}: must be OPTIONAL'.format(self.function_id,
                                                                                           self.step_number)
        }

    def test_invalid_response_point(self):
        step_json = self.step_json
        step_json.update({
            'response': 'invalid_point'
        })
        exception = self.validate_step_definition(step_json)
        assert exception == {
            'key': 'AttributeError',
            'error': 'Response point in function {} step {} does not match point definition. '
                     'Error=No point named invalid_point'.format(self.function_id, self.step_number)
        }


class TestFunctionDefinition:
    """Regression tests for Function Definition."""

    @property
    def function_json(self):
        """Return function enable_high_voltage_ride_through_mode"""
        return copy.deepcopy(enable_high_voltage_ride_through_mode)

    @staticmethod
    def validate_function_definition(function_json):
        exception = {}
        try:
            FunctionDefinition(POINT_DEFINITIONS, function_json)
        except Exception as err:
            exception['key'] = type(err).__name__
            exception['error'] = str(err)
        return exception

    def test_valid_function_definition(self):
        exception = self.validate_function_definition(self.function_json)
        assert exception == {}

    def test_missing_function_id(self):
        """Test raising exception if function missing id"""
        function_json = self.function_json
        function_json.pop('id')
        exception = self.validate_function_definition(function_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Missing function ID'
        }

    def test_missing_function_steps(self):
        """Test raising exception if function missing steps"""
        function_json = self.function_json
        function_json.pop('steps')
        exception = self.validate_function_definition(function_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Missing steps for function {}'.format(self.function_json['id'])
        }

    def test_duplicated_step_number(self):
        """Test raising exception if there is duplicated step_number in function"""
        function_json = self.function_json
        function_json['steps'][2].update({
            'step_number': 1
        })
        exception = self.validate_function_definition(function_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Duplicated step number 1 for function {}'.format(self.function_json['id'])
        }

    def test_missing_a_step(self):
        """Test raising exception if function missing a step"""
        function_json = self.function_json
        del function_json['steps'][1]
        exception = self.validate_function_definition(function_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'There are missing steps for function {}'.format(self.function_json['id'])
        }

    def test_selector_block_function(self):
        """Test raising exception if one step in selector block function is optional"""
        function_json = copy.deepcopy(curve_selector_block)
        exception = self.validate_function_definition(function_json)
        assert exception == {}

        # Change step 2 to optional
        function_json['steps'][1]['optional'] = 'O'
        exception = self.validate_function_definition(function_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Function curve - Step 2: optionality must be either INITIALIZE or MANDATORY'
        }


class TestFunctionDefinitions:
    """Regression tests for Function Definitions."""

    @property
    def functions_json(self):
        return [
            copy.deepcopy(enable_high_voltage_ride_through_mode),
            copy.deepcopy(curve_selector_block)
        ]

    @staticmethod
    def validate_functions_definition(functions_json):
        exception = {}
        try:
            function_definitions = FunctionDefinitions(POINT_DEFINITIONS)
            function_definitions.load_functions(functions_json)
        except Exception as err:
            exception['key'] = type(err).__name__
            exception['error'] = str(err)
        return exception

    def test_load_functions_yaml(self):
        try:
            FunctionDefinitions(POINT_DEFINITIONS, FUNCTION_DEFINITIONS_PATH)
            assert True
        except ValueError:
            assert False

    def test_valid_functions_definitions(self):
        exception = self.validate_functions_definition(self.functions_json)
        assert exception == {}

    def test_duplicated_function_id(self):
        """Test raising exception if there are multiple function with same id"""
        functions_json = self.functions_json
        functions_json[1]['id'] = self.functions_json[0]['id']
        exception = self.validate_functions_definition(functions_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Problem parsing FunctionDefinitions. '
                     'Error=There are multiple functions for function id {}'.format(functions_json[1]['id'])
        }

    def test_invalid_func_ref(self):
        """Test raising exception if a step has an invalid func_ref"""
        functions_json = self.functions_json
        functions_json[0]['steps'][3]['func_ref'] = 'invalid_curve'
        exception = self.validate_functions_definition(functions_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Invalid Function Reference invalid_curve for Step 4 '
                     'in Function enable_high_voltage_ride_through_mode'
        }
