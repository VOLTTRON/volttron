# import os
# import sys
# from volttrontesting.fixtures.volttron_platform_fixtures import *
# from volttrontesting.fixtures.vc_fixtures import *
#
#
# def get_main_path(item_path):
#     """
#     Retrieve the directory above the tests that are being executed i.e. the
#     level above ./tests.
#
#     :param item_path: A collection item fs path (item.fspath)
#     :return: An absolute path to the directory above tests.
#     """
#     return os.path.abspath(os.path.dirname(os.path.dirname(item_path)))
#
# #
# # def pytest_runtest_protocol(item, nextitem):
# #     sys.path.insert(0, get_main_path(item.fspath))
#
# def pytest_configure(config):
#     import sys
#     sys._called_from_test = True
#
# def pytest_unconfigure(config):
#     import sys
#     del sys._called_from_test
#
# def pytest_collect_file(parent, path):
#     if path.ext == ".py" and path.basename.startswith("test"):
#         return VolttronTestFile(path, parent)
#
# # def pytest_prepare_exc(**kwargs):
# #     print(kwargs)
#
# class VolttronTestFile(pytest.File):
#     def __init__(self, path, parent):
#         super(VolttronTestFile, self).__init__(path, parent)
#         sys.path.insert(0, get_main_path(path.strpath))
#     def collect(self):
#
#         yield VolttronTestItem(self.name, self.parent)
#         # import yaml  # we need a yaml parser, e.g. PyYAML
#         # raw = yaml.safe_load(self.fspath.open())
#         # for name, spec in raw.items():
#         #     yield YamlItem(name, self, spec)
#
#
# class VolttronTestItem(pytest.Item):
#     def __init__(self, name, parent):
#         super(VolttronTestItem, self).__init__(name, parent)
#
#
#     def runtest(self):
#         print("Running: {}".format(self.name))
#         # for name, value in self.spec.items():
#         #     # some custom test execution (dumb example follows)
#         #     if name != value:
#         #         raise YamlException(self, name, value)
#
#
# # class PythonFile(pytest.File):
# #     def collect(self):
# #         import yaml # we need a yaml parser, e.g. PyYAML
# #         raw = yaml.safe_load(self.fspath.open())
# #         for name, spec in raw.items():
# #             yield YamlItem(name, self, spec)
# #
# # class YamlItem(pytest.Item):
# #     def __init__(self, name, parent, spec):
# #         super(YamlItem, self).__init__(name, parent)
# #         self.spec = spec
# #
# #     def runtest(self):
# #         for name, value in self.spec.items():
# #             # some custom test execution (dumb example follows)
# #             if name != value:
# #                 raise YamlException(self, name, value)
# #
# #     def repr_failure(self, excinfo):
# #         """ called when self.runtest() raises an exception. """
# #         if isinstance(excinfo.value, YamlException):
# #             return "\n".join([
# #                 "usecase execution failed",
# #                 "   spec failed: %r: %r" % excinfo.value.args[1:3],
# #                 "   no further details known at this point."
# #             ])
# #
# #     def reportinfo(self):
# #         return self.fspath, 0, "usecase: %s" % self.name
# #
# # def pytest_runtest_setup(item):
# #     """
# #     This hook is called every time a setup->test->teardown cycle is created.
# #
# #     The hook will verify that the directory above the currently scheduled test
# #     is added to the system path.  This is mainly so we don't have to add it
# #     for every non module test in services/core/Foo.
# #
# #     :param item: Item is a pytest Collection item.
# #     :return:
# #     """
# #     main_path = get_main_path(item.fspath)
# #     if main_path not in sys.path:
# #         sys.path.insert(0, main_path)
# #
# #
# def pytest_runtest_teardown(item, nextitem):
#     main_path = get_main_path(item.fspath.strpath)
#     sys.path.remove(main_path)
