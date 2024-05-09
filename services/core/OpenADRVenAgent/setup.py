# Always prefer setuptools over distutils

from os import path
from setuptools import setup, find_packages

MAIN_MODULE = "agent"

# Find the agent package that contains the main module
packages = find_packages(".")
agent_package = ""
for package in find_packages():
    # Because there could be other packages such as tests
    if path.isfile(package + "/" + MAIN_MODULE + ".py"):
        agent_package = package
        break

if not agent_package:
    raise RuntimeError(
        f"None of the packages under {path.abspath('.')} contain the file {MAIN_MODULE}.py"
    )

# Find the version number from the main module
agent_module = f"{agent_package}.{MAIN_MODULE}"
_temp = __import__(agent_module, globals(), locals(), ["__version__"], 0)
__version__ = _temp.__version__

setup(
    name=f"{agent_package}agent",
    version=__version__,
    install_requires=["volttron"],
    packages=packages,
    entry_points={"setuptools.installation": [f"eggsecutable = {agent_module}:main"]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Home Automation",
        "Topic :: Software Development :: Embedded Systems",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
