import sys,time,os,pytest
sys.path.append(os.path.dirname(os.path.realpath(__file__))+ "/../../")
import rticonnextdds_connector as rti

class TestConnector:
  """
  This class tests the correct instantiation of 
  :class:`rticonnextdds_connector.Connector` object. 
  """

  def test_invalid_xml_path(self):
    """
    This test function ensures that a ValueError is raised if
    an incorrect xml path is passed to the 
    Connector constructor.
    """
    participant_profile = "MyParticipantLibrary::Zero"
    invalid_xml_path = "invalid/path/to/xml"
    with pytest.raises(ValueError):
      connector = rti.Connector(participant_profile,invalid_xml_path)
  
  def test_invalid_participant_profile(self):
    """
    This test function ensures that a ValueError is raised if
    an invalid participant profile name is passed to the 
    Connector constructor.
    """
    invalid_participant_profile = "InvalidParticipantProfile"  
    xml_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
      "../xml/ShapeExample.xml")
    with pytest.raises(ValueError):
      connector = rti.Connector(invalid_participant_profile,xml_path)
  
  def test_ivalid_xml_profile(self):
    """
    This test function ensures that a ValueError is raised if
    an invalid xml file is passed to the 
    Connector constructor.
    """
    participant_profile = "MyParticipantLibrary::Zero"
    invalid_xml = os.path.join(os.path.dirname(os.path.realpath(__file__)),
      "../xml/InvalidXml.xml")
    with pytest.raises(ValueError):
      connector = rti.Connector(participant_profile,invalid_xml)
  
  def test_connector_creation(self,rtiConnectorFixture):
    """
    This function tests the correct instantiation of 
    Connector object.

    :param rtiConnectorFixture: :func:`conftest.rtiConnectorFixture`
    :type rtiConnectorFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    """
    assert rtiConnectorFixture!=None and isinstance(rtiConnectorFixture,\
      rti.Connector)
  
  def test_multiple_connector_creation(self):
    """
    This function tests the correct instantiation of multiple
    Connector objects in succession.
    """
    connectors = []
    xml_path= os.path.join(os.path.dirname(os.path.realpath(__file__)),
      "../xml/ShapeExample.xml") 
    participant_profile="MyParticipantLibrary::Zero"
    for i in range (0,5):
     connectors.append(rti.Connector(participant_profile,xml_path))
    assert all( x!=None and isinstance(x,rti.Connector) for x in connectors) 
