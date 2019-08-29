import pytest
try:
    import dnp3
except ImportError:
    pytest.skip("pydnp3 not found!", allow_module_level=True)

import copy

from dnp3.points import PointDefinition, ArrayHeadPointDefinition, PointDefinitions, PointValue

from test_mesa_agent import POINT_DEFINITIONS_PATH, FUNCTION_DEFINITIONS_PATH


AO_4 = {
    'index': 4,
    'description': 'Power Factor Sign convention',
    'data_type': 'AO',
    'common_data_class': 'ENG',
    'maximum': 2,
    'ln_class': 'MMXU',
    'units': 'None',
    'minimum': 1,
    'data_object': 'PFSign',
    'allowed_values': {
        '1': 'IEC active power',
        '2': 'IEEE lead/lag'
    },
    'type': 'enumerated',
    'name': 'MMXU.PFSign.AO4'
}

AO_244 = {
    'index': 244,
    'description': 'Curve Edit Selector. Writing to this point selects '
                   'which of the curves can currently be viewed and changed.',
    'data_type': 'AO',
    'common_data_class': 'ORG',
    'ln_class': 'DGSM',
    'minimum': 1,
    'data_object': 'InCrv',
    'name': 'DGSMn.InCrv.AO244',
    'type': 'selector_block',
    'selector_block_start': 244,
    'selector_block_end': 448
    }


class TestPointDefinition:

    @property
    def point_json(self):
        return copy.deepcopy(AO_4)

    @staticmethod
    def validate_point_definition(point_json):
        exception = {}
        try:
            PointDefinition(point_json)
        except Exception as err:
            exception['key'] = type(err).__name__
            exception['error'] = str(err)
        return exception

    def test_valid_point_definition(self):
        exception = self.validate_point_definition(self.point_json)
        assert exception == {}

    def test_missing_point_name(self):
        """Test raising exception if point definition missing point name"""
        point_json = self.point_json
        point_json.pop('name')
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Missing point name'
        }

    def test_missing_index(self):
        """Test raising exception if point definition missing point index"""
        point_json = self.point_json
        point_json.pop('index')
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Missing index for point {}'.format(self.point_json['name'])
        }

    def test_missing_data_type(self):
        """Test raising exception if point definition missing data_type"""
        point_json = self.point_json
        point_json.pop('data_type')
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Missing data type for point {}'.format(self.point_json['name'])
        }
        
    def test_invalid_event_class(self):
        """Test raising exception if event_class is not 0, 1, 2, or 3"""
        point_json = self.point_json
        point_json.update({
            'event_class': 4
        })
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Invalid event class 4 for point {}'.format(self.point_json['name'])
        }

    def test_invalid_type(self):
        """Test raising exception if type is not array, selector_block, or enumerated"""
        point_json = self.point_json
        point_json.update({
            'type': 'regular'
        })
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Invalid type regular for point {}'.format(self.point_json['name'])
        }

    def test_missing_response(self):
        """Test raising exception if the point action is publish_and_respond but missing response field"""
        point_json = self.point_json
        point_json.update({
            'action': 'publish_and_respond'
        })
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Missing response point name for point {}'.format(self.point_json['name'])
        }

    def test_missing_allowed_values(self):
        """Test raising exception if the enumerated type missing allowed_values map"""
        point_json = self.point_json
        point_json.pop('allowed_values')
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'Missing allowed values mapping for point {}'.format(self.point_json['name'])
        }

    def test_invalid_defined_selector_block_start(self):
        """Test raising exception if selector_block_start defined for non-selector-block point"""
        point_json = self.point_json
        point_json.update({
            'selector_block_start': 244
        })
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'selector_block_start defined for non-selector-block point {}'.format(self.point_json['name'])
        }

    def test_invalid_defined_selector_block_end(self):
        """Test raising exception if selector_block_end defined for non-selector-block point"""
        point_json = self.point_json
        point_json.update({
            'selector_block_end': 448
        })
        exception = self.validate_point_definition(point_json)
        assert exception == {
            'key': 'ValueError',
            'error': 'selector_block_end defined for non-selector-block point {}'.format(self.point_json['name'])
        }


class TestPointDefinitions:
    """Regression tests for the Mesa Agent."""

    def test_load_points_from_json_file(self):
        try:
            PointDefinitions(point_definitions_path=POINT_DEFINITIONS_PATH)
            assert True
        except ValueError:
            assert False