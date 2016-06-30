# Python Testing Documentation

To run the tests for python binding of **rticonnextdds_connector**:

1. Install [pytest](https://pytest.org/latest/contents.html) with:

  ``pip install pytest``

2. To execute all the tests, issue the following command from the base directory: 
  
   ``py.test ./test/python``
  
   To execute each test individually, also include the name of the test file: 
  
   ``py.test ./test/python/test_rticonnextdds_input.py``

**Note:** Some tests are marked to fail with ``@pytest.mark.xfail`` annotation either because those tests are expected to fail due to implicit type conversion or because the functionality being tested is not yet supported by the python connector library. These tests will be reported as ``xfail``.


All the tests are documented in their respective source files following the [docstrings](https://www.python.org/dev/peps/pep-0257/)
convention. [Sphinx apidoc](http://www.sphinx-doc.org/en/stable/man/sphinx-apidoc.html) can be used for automatically generating the test API documentation. 

Python tests are organized as follows:

1. ``conftest.py``: Contains [pytest fixtures](https://pytest.org/latest/fixture.html) that are used for configuring the tests.
2. ``test_rticonnextdds_connector.py``: Contains tests for ``rticonnextdds_connector.Connector`` object
3. ``test_rticonnextdds_input.py``: Contains tests for ``rticonnextdds_connector.Input`` object
3. ``test_rticonnextdds_output.py``: Contains tests for ``rticonnextdds_connector.Output`` object
4. ``test_rticonnextdds_dataflow.py``: Tests the dataflow between an ``rticonnextdds_connector.Input`` and ``rticonnextdds_connector.Output`` object.
