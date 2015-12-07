#!/bin/sh

env/bin/activate
pip install pytest pytest-bdd pytest-cov

py.test
