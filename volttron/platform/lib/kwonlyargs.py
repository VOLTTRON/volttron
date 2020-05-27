'''Support functions for implementing keyword-only arguments.

This module is designed to make it easy to support keyword-only
arguments in Python 2.7 while providing the same kind of exceptions one
would see with Python 3.x.

Basic usage:

.. code-block:: python

    def foo(arg1, *args, **kwargs):
        # Use required context manager to convert KeyError exceptions
        # to TypeError with an appropriate message.
        with required:
            arg2 = kwargs.pop('arg2')
            arg3 = kwargs.pop('arg3')
        # Provide a default to pop for optional arguments
        arg4 = kwargs.pop('arg4', 'default value')
        # Include the next line to disallow additional keyword args
        assertempty(kwargs)

'''

__all__ = ['required', 'assertempty']


class Required(object):
    '''Context manager to raise TypeError for missing required kwargs.'''
    __slots__ = ()
    @classmethod
    def __enter__(cls):
        pass
    @classmethod
    def __exit__(cls, exc_type, exc_value, exc_tb):
        # pylint: disable=bad-context-manager
        if exc_type is KeyError:
            raise TypeError(
                'missing a required keyword-only argument %r' % exc_value.args)

required = Required()   # pylint: disable=invalid-name


def assertempty(kwargs):
    '''Raise TypeError if kwargs is not empty.'''
    if kwargs:
        name = next(iter(kwargs))
        raise TypeError('got an unexpected keyword argument %r' % (name,))
