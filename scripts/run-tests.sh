#!/bin/sh

# The context should already have been activated at this point.

pip install pytest pytest-bdd pytest-cov

py.test
