.. _Python-for-Matlab-Users:

=======================
Python for Matlab Users
=======================

Matlab is a popular proprietary programming language and tool suite with built in support for matrix operations and
graphically plotting computation results.  The purpose of this document is to introduce Python to those already familiar
Matlab so it will be easier for them to develop tools and agents in VOLTTRON.


A Simple Function
-----------------

Python and Matlab are similar in many respects, syntactically and semantically.  With the addition of the NumPy library
in Python, almost all numerical operations in Matlab can be emulated or directly translated. Here are functions in each
language that perform the same operation:

.. code-block:: matlab

   % Matlab
   function [result] = times_two(number)
       result = number * 2;
   end

.. code-block:: python

   # Python
   def times_two(number):
       result = number * 2
       return result

Some notes about the previous functions:

#. Values are explicitly returned with the `return` statement. It is possible to return multiple values, as in Matlab,
   but doing this without a good reason can lead to overcomplicated functions.

#. Semicolons are not used to end statements in python, and white space is significant. After a block is started (if,
   for, while, functions, classes) subsequent lines should be indented with four spaces.  The block ends when the
   programmer stops adding the extra level of indentation.


Translating
-----------

The following may be helpful if you already have a Matlab file or function that will be translated into Python.  Many of
the syntax differences between Matlab and Python can be rectified with your text editor's find and replace feature.

Start by copying all of your Matlab code into a new file with a `.py` extension.  It is recommended to start by
commenting everything out and uncommenting the Matlab code in chunks.  This way it is possible to write valid Python and
verify it as you translate, instead of waiting till the whole file is "translated".  Editors designed to work with
Python should be able to highlight syntax errors as well.

#. Comments are created with a `%`. Find and replace these with `#`.

.. code-block:: python

    def test_function():
        # single line Python comment
        """
        Multi-line Python comment
        """
        pass # inline Python comment

#. Change `elseif` blocks to `elif` blocks.

.. code-block:: python

    if thing == 0:
        do_thing1()
    elif thing ==1:
        do_thing2()
    else:
        do_the_last_thing()

#. Python indexes start at zero instead of one.  Array slices and range operations don't include the upper bound, so
   only the lower bound should decrease by one.  The following examples are of Python code in the console:

.. code-block:: console

    >>> test_array = [0, 1, 2, 3, 4]
    >>> test_array[0]
    0
    >>> test_array[1]
    1
    >>> test_array[0:2]
    [0, 1]
    >>>>>> test_array[:2]
    [0, 1]
    >>> test_array[2:]
    [2, 3, 4]
    >>>

#. Semicolons in Matlab are used to suppress output at the end of lines and for organizing array literals. After
   arranging the arrays into nested lists, all semicolons can be removed.

#. The `end` keyword in Matlab is used both to access the last element in an array and to close blocks. The array use
   case can be replaced with `-1` and the others can be removed entirely.

.. code-block:: console

    >>> test_array = [0, 1, 2, 3, 4]
    >>> test_array[-1]
    4
    >>>


A More Concrete Example
^^^^^^^^^^^^^^^^^^^^^^^

In the `Building Economic Dispatch <https://github.com/VOLTTRON/econ-dispatch>`_ project, a sibling project to VOLTTRON,
a number of components written in Matlab would create a matrix out of some collection of columns and perform least
squares regression using the `matrix division` operator.  This is straightforward and very similar in both languages
assuming that all of the columns are defined and are the same length.

.. code-block:: matlab

   % Matlab
   XX = [U, xbp, xbp2, xbp3, xbp4, xbp5];
   AA = XX \ ybp;

.. code-block:: python

   # Python
   import numpy as np

   XX = np.column_stack((U, xbp, xbp2, xbp3, xbp4, xbp5))
   AA, resid, rank, s = np.linalg.lstsq(XX, ybp)

This pattern also included the creation of the `U` column, a column of ones used as the bias term in the linear equation
.  In order to make the Python version more readable and more robust, the pattern was removed from each component and
replaced with a single function call to `least_squares_regression`.

This function does some validation on the input parameters, automatically creates the bias column, and returns the least
squares solution to the system.  Now if we want to change how the solution is calculated we only have to change the one
function, instead of each instance where the pattern was written originally.

.. code-block:: python

   def least_squares_regression(inputs=None, output=None):
       if inputs is None:
           raise ValueError("At least one input column is required")
       if output is None:
           raise ValueError("Output column is required")

       if type(inputs) != tuple:
           inputs = (inputs,)

       ones = np.ones(len(inputs[0]))
       x_columns = np.column_stack((ones,) + inputs)

       solution, resid, rank, s = np.linalg.lstsq(x_columns, output)
       return solution

Lessons Learned (sometimes the hard way)
----------------------------------------


Variable Names
^^^^^^^^^^^^^^

Use descriptive function and variable names whenever possible. The most important things to consider here are reader
comprehension and searching.  Consider a  variable called `hdr`.  Is it `header` without any vowels, or is it short for
`high-dynamic-range`?  Spelling out full words in variable names can save someone else a lot of guesswork.

Searching comes in when we're looking for instances of a string or variable.  Single letter variable names are
impossible to search for.  Variables names describing the value being stored in a concise but descriptive manner are
preferred.


Matlab load/save
^^^^^^^^^^^^^^^^

Matlab has built-in functions to automatically save and load variables from your programs to disk.  Using these
functions can lead to poor program design and should be avoided if possible.  It would be best to refactor as you
translate if they are being used.  Few operations are so expensive that that cannot be redone every time the program is
run.  For part of the program that saves variables, consider making a function that simply returns them instead.

If your Matlab program is loading csv files then use the Pandas library when working in python.  Pandas works well with
NumPy and is the go-to library when using csv files that contain numeric data.


More Resources
--------------

`NumPy for Matlab Users
<https://docs.scipy.org/doc/numpy-dev/user/numpy-for-matlab-users.html>`_
Has a nice list of common operations in Matlab and NumPy.

`NumPy Homepage
<http://www.numpy.org/>`_

`Pandas Homepage
<http://pandas.pydata.org/>`_
