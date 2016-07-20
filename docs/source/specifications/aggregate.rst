=======================================
Aggregate Historian Agent Specification
=======================================

Description
===========

An aggregate historian computes aggregates of data stored in a given volttron
historian's data store. It runs periodically to compute aggregate data
and store it in new tables/collections in the historian's data store. Each
regular historian ( `BaseHistorian <../apidocs/volttron/volttron.platform.agent.html#module-volttron.platform.agent.base_historian>`_ )
needs a corresponding aggregate historian to compute and store aggregates of
the data collected by the regular historian.


.. image:: files/aggregate_historian.jpg


Software Interfaces
===================

**Data Collection** - Data store that the aggregate historian uses as input source needs to be up. Access to it should be provided using an account that has create, read, and write privileges. For example, a MongoAggregateHistorian needs to be able to connect to the mongodb used by MongoHistorian using an account that has read and write access to the db used by the MongoHistorian.

**Data retrieval** - Aggregate Historian Agent does not provide api for retrieving the aggregate data collected. Use Historian agent's query interface

User Interfaces
===============

Aggregation agent requires user to configure the following details as part of the agent configuration file

1. Connection details for historian's data store (same as historian agent configuration)
2. List of aggregation groups where each group contains:
    1. Aggregation period which can be minutes, hours, days, weeks or months
    2. Boolean parameter to indicate if aggregation periods should align to calendar times
    3. List of aggregation points with topic name, type of aggregation (sum, avg, etc.), and minimum number of records that should be available for the aggregate to be computed


Functional Capabilities
=======================

1. Should run periodically to compute aggregate data.
2. Same instance of the agent should be able to collect data at more than one time interval
3. For each configured time period/interval agent should be able to collect different type of aggregation for different topics/points
4. Support aggregation over multiple topics/points
5. Agent should be able to handle and normalize different time units such as minutes, hours, days, weeks and months
6. Agent should be able to compute aggregate both based on wall clock based time intervals and calendar based time interval. For example, agent should be able to calculate daily average based on 12.00AM to 11.59PM of a calendar day or between current time and the same time the previous day.
7. Data should be stored in such a way

Data Structure
==============

Collected aggregate data should be stored in the historian data store into new collection or tables and should be accessible by historian agent's query interface. Users should easily be able to query aggregate data of multiple points for which data is time synchronized.

Constraints and Limitations
===========================

1. Initial implementation of this agent will not support any data filtering for raw data before computing data aggregation



    **MySQL**

    ================ ==============
          Name        Description
    ================ ==============
    AVG()            Return the average value of the argument
    BIT_AND()        Return bitwise AND
    BIT_OR()         Return bitwise OR
    BIT_XOR()        Return bitwise XOR
    COUNT()          Return a count of the number of rows returned
    GROUP_CONCAT()   Return a concatenated string
    MAX()            Return the maximum value
    MIN()            Return the minimum value
    STD()            Return the population standard deviation
    STDDEV()         Return the population standard deviation
    STDDEV_POP()     Return the population standard deviation
    STDDEV_SAMP()    Return the sample standard deviation
    SUM()            Return the sum
    VAR_POP()        Return the population standard variance
    VAR_SAMP()       Return the sample variance
    VARIANCE()       Return the population standard variance
    ================ ==============


    **SQLite**

    ================ ==============
          Name        Description
    ================ ==============
    AVG()            Return the average value of the argument
    COUNT()          Return a count of the number of rows returned
    GROUP_CONCAT()   Return a concatenated string
    MAX()            Return the maximum value
    MIN()            Return the minimum value
    SUM()            Return sum of all non-NULL values in the group. If there are no non-NULL input rows then returns NULL .
    TOTAL()          Return sum of all non-NULL values in the group.If there are no non-NULL input rows returns 0.0
    ================ ==============


    **MongoDB**

    ================ ==============
          Name        Description
    ================ ==============
    SUM              Returns a sum of numerical values. Ignores non-numeric values
    AVG              Returns a average of numerical values. Ignores non-numeric values
    MAX              Returns the highest expression value for each group.
    MIN              Returns the lowest expression value for each group.
    FIRST            Returns a value from the first document for each group. Order is only defined if the documents are in a defined order.
    LAST             Returns a value from the last document for each group. Order is only defined if the documents are in a defined order.
    PUSH             Returns an array of expression values for each group
    ADDTOSET         Returns an array of unique expression values for each group. Order of the array elements is undefined.
    STDDEVPOP        Returns the population standard deviation of the input values
    STDDEVSAMP       Returns the sample standard deviation of the input values
    ================ ==============


2. Initial implementation should support all aggregation types directly supported by underlying data store. End user input is needed to figure out what additional aggregation methods are to be supported
