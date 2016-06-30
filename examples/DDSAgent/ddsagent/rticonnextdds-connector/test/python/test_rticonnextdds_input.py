import pytest,sys,os
sys.path.append(os.path.dirname(os.path.realpath(__file__))+ "/../../")
import rticonnextdds_connector as rti

class TestInput:
  """
  This class tests the correct instantiation of 
  :class:`rticonnextdds_connector.Input` object. 

  .. todo:: 
 
       * Move :func:`rticonnextdds_connector.Input.wait` to 
         :class:`rticonnextdds_connector.Connector` 

  """

  def test_invalid_DR(self,rtiConnectorFixture):
    """
    This test function ensures that a ValueError is raised if
    an incorrect DataReader name is passed to the
    Input constructor.

    :param rtiConnectorFixture: :func:`conftest.rtiConnectorFixture`
    :type rtiConnectorFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_

    """
    invalid_DR = "InvalidDR"
    with pytest.raises(ValueError):
       rtiConnectorFixture.getInput(invalid_DR)
  
  def test_creation_DR(self,rtiInputFixture):
    """
    This function tests the correct instantiation of 
    Input object.

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    """
    assert rtiInputFixture!=None and isinstance(rtiInputFixture,rti.Input) \
      and rtiInputFixture.name == "MySubscriber::MySquareReader" \
      and isinstance(rtiInputFixture.connector,rti.Connector) \
      and isinstance(rtiInputFixture.samples,rti.Samples) \
      and isinstance(rtiInputFixture.infos,rti.Infos)
