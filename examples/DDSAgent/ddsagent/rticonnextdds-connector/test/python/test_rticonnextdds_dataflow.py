import pytest,time,sys,os
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../../")
import rticonnextdds_connector as rti

class TestDataflow:
  """
  This class tests the flow of data between 
  an :class:`rticonnextdds_connector.Input` and an
  :class:`rticonnextdds_connector.Output` object.
 
  .. todo::

       * No Exception is thrown when a non-existent field is 
         accessed. ``AttributeError`` must be propagated 
         to the user when a non-existent field is accessed with
         :func:`rticonnextdds_connector.Samples.getNumber`,
         :func:`rticonnextdds_connector.Samples.getString`,
         and :func:`rticonnextdds_connector.Samples.getBoolean`.

       * Address Segmentation fault on 0-index and out-of-bound access on
         :class:`rticonnextdds_connector.Infos` and :class:`rticonnextdds_connector.Samples`.

       * Behavior on inconsistent type access needs to be addressed:

           * Calling :func:`rticonnextdds_connector.Samples.getString` on Numeric field gives 
             a string representation of the number and on a Boolean field gives None 

           * Calling :func:`rticonnextdds_connector.Samples.getBoolean` on String or Numeric field
             gives an int with value of 0/1 and on a Boolean filed returns an int value of 0/1

           * Calling :func:`rticonnextdds_connector.Samples.getNumber` on a Boolean field 
             gives a float value of 0.0 and on String field gives a float value of 0.0 
  """
  @pytest.fixture(scope="class")
  def testMsg(self):
    """
    A class-scoped `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    which instantiates a test message to test the flow of data between an Input and Output object.
    
    :returns: A class scoped test message 
    :rtype: `Dictionary <https://docs.python.org/3/tutorial/datastructures.html#dictionaries>`_
    
    """
    return {"x":1,"y":1,"z":True,"color":"BLUE","shapesize":5}

  @pytest.fixture(autouse=True,params=[{"wait":True,"method":"read"},
    {"wait":True,"method":"take"},{"wait":False,"method":"read"},
    {"wait":False,"method":"take"}])
  def sendTestMsg(self,request,rtiInputFixture,rtiOutputFixture,testMsg):
    """
    An `autouse <https://pytest.org/latest/fixture.html#autouse-fixtures-xunit-setup-on-steroids>`_ 
    `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    which is executed before any test function in :class:`TestDataflow` class  is executed.
    This fixture method uses session-scoped Input and Output objects to set-up the dataflow test.
    First any pre-existing messages in the middleware cache are taken and then the Output object
    sends one test message to the Input object. This fixture is 
    `parameterized <https://pytest.org/latest/fixture.html#parametrizing-a-fixture>`_, 
    so that each test is executed four times- first, where the Input object waits for 10 seconds
    for data and uses :func:`rticonnextdds_connector.Input.read` method to obtain the sent test message; 
    second, where the Input object waits for 10 seconds for data to arrive and 
    uses :func:`rticonnextdds_connector.Input.take` method to obtain the sent message; third, where Input
    object does not wait but uses :func:`rticonnextdds_connector.Input.read` method to obtain the sent message; 
    and finally, where Input object does not wait and uses 
    :func:`rticonnextdds_connector.Input.take` method to obtain the sent message.

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    :param rtiOutputFixture: :func:`conftest.rtiOutputFixture`
    :type rtiOutputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    :param testMsg: :func:`testMsg`
    :type testMsg: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    
    """
    # take any pre-existing samples from cache
    rtiInputFixture.take()
    rtiOutputFixture.instance.setDictionary(testMsg)
    rtiOutputFixture.write()
    wait=request.param.get('wait')
    method=request.param.get('method')

    if wait:
       rtiInputFixture.wait(10)
       retrieve_func= getattr(rtiInputFixture,method)
       retrieve_func() 
    else:
      # loop to allow sometime for discovery of Input and Output objects
      for i in range(1,20):
          time.sleep(.5)
          retrieve_func= getattr(rtiInputFixture,method)
          retrieve_func() 
          if rtiInputFixture.samples.getLength() > 0:
            break

  def test_samples_getLength(self,rtiInputFixture):
    """
    This function tests the correct operation of 
    :func:`rticonnextdds_connector.Samples.getLength` 

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    """
    assert rtiInputFixture.samples.getLength() == 1 

  def test_infos_getLength(self,rtiInputFixture):
    """
    This function tests the correct operation of 
    :func:`rticonnextdds_connector.Infos.getLength` 

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    """
    assert rtiInputFixture.infos.getLength() == 1 

  def test_infos_isValid(self,rtiInputFixture):
    """
    This function tests the correct operation of 
    :func:`rticonnextdds_connector.Infos.isValid` 

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    """
    assert rtiInputFixture.infos.isValid(1)== True

  def test_getDictionary(self,rtiInputFixture,testMsg):
    """
    This function tests the correct operation of 
    :func:`rticonnextdds_connector.Samples.getDictionary`.
    Received message should be the same as the :func:`testMsg` 

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    :param testMsg: :func:`testMsg`
    :type testMsg: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    """
    received_msg = rtiInputFixture.samples.getDictionary(1)
    assert received_msg==testMsg

  def test_getTypes(self,rtiInputFixture,testMsg):
    """
    This function tests the correct operation of 
    :func:`rticonnextdds_connector.Samples.getString`,
    :func:`rticonnextdds_connector.Samples.getNumber` and
    :func:`rticonnextdds_connector.Samples.getBoolean`.
    Received values should be the same as that of :func:`testMsg`

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    :param testMsg: :func:`testMsg`
    :type testMsg: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    """
    x = rtiInputFixture.samples.getNumber(1,"x")
    y = rtiInputFixture.samples.getNumber(1,"y")
    z = rtiInputFixture.samples.getBoolean(1,"z")
    color  = rtiInputFixture.samples.getString(1,"color")
    shapesize = rtiInputFixture.samples.getNumber(1,"shapesize")
    assert x == testMsg['x'] and y == testMsg['y'] \
      and z == testMsg['z'] and color == testMsg['color'] \
      and shapesize == testMsg['shapesize']

  @pytest.mark.xfail
  def test_getNumber_for_nonexistent_field(self,rtiInputFixture,testMsg):
    """
    This function tests that an ``AttributeError`` is raised when a non-existent field
    is accessed with :func:`rticonnextdds_connector.Samples.getNumber`

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    :param testMsg: :func:`testMsg`
    :type testMsg: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_

    .. note: This test is marked to fail as this case is not handled yet.
    """
    with pytest.raises(AttributeError) as execinfo:
      x = rtiInputFixture.samples.getNumber(1,"invalid_field")
    print("\nException of type:"+str(execinfo.type)+\
      "\nvalue:"+str(execinfo.value))

  @pytest.mark.xfail(sys.version_info < (3,0), reason="for python >= 3, fromcstring raises AttributeError when decode is called on NoneType returned by rtin_RTIDDSConnector_getStringFromSamples on nonexistent field")
  def test_getString_for_nonexistent_field(self,rtiInputFixture,testMsg):
    """
    This function tests that an ``AttributeError`` is raised when a non-existent field
    is accessed with :func:`rticonnextdds_connector.Samples.getString`

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    :param testMsg: :func:`testMsg`
    :type testMsg: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_

    .. note: This test is marked to fail as this case is not handled yet.
    """
    with pytest.raises(AttributeError) as execinfo:
      x = rtiInputFixture.samples.getString(1,"invalid_field")
    print("\nException of type:"+str(execinfo.type)+\
      "\nvalue:"+str(execinfo.value))

  @pytest.mark.xfail
  def test_getBoolean_for_nonexistent_field(self,rtiInputFixture,testMsg):
    """
    This function tests that an ``AttributeError`` is raised when a non-existent field
    is accessed with :func:`rticonnextdds_connector.Samples.getBoolean`

    :param rtiInputFixture: :func:`conftest.rtiInputFixture`
    :type rtiInputFixture: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
    :param testMsg: :func:`testMsg`
    :type testMsg: `pytest.fixture <https://pytest.org/latest/builtin.html#_pytest.python.fixture>`_
  
    .. note: This test is marked to fail as this case is not handled yet.
    """
    with pytest.raises(AttributeError) as execinfo:
      x = rtiInputFixture.samples.getBoolean(1,"invalid_field")
    print("\nException of type:"+str(execinfo.type)+\
      "\nvalue:"+str(execinfo.value))
