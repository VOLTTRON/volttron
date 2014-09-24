from __future__ import print_function

import os
import subprocess
import sys


_path = os.path.dirname(__file__) or os.getcwd()
_envdir = os.path.join(_path, 'env')
_prompt = '(volttron) '


def stage1(directory=_envdir, prompt=_prompt):
    import contextlib
    import re
    import shutil
    import tarfile
    import tempfile
    import urllib2

    class EnvBuilder(object):
        def __init__(self, version=None, prompt=None):
            self.version = version
            self.prompt = prompt
            self.env_exe = None

        def _fetch(self, url):
            response = urllib2.urlopen(url)
            if response.getcode() != 200:
                print('Server response:', response.code,
                      response.msg, file=sys.stderr)
                print('Error: Download failed!', file=sys.stderr)
                sys.exit(1)
            return response

        def get_version(self):
            print('Downloading virtualenv DOAP record')
            doap_url = 'https://pypi.python.org/pypi?:action=doap&name=virtualenv'
            with contextlib.closing(self._fetch(doap_url)) as response:
                doap_xml = response.read()
            self.version = re.search(
                    r'<revision>([^<]*)</revision>', doap_xml).group(1)
            return self.version

        def download(self, directory):
            if self.version is None:
                self.get_version()
            url = ('https://pypi.python.org/packages/source/v/virtualenv/' +
                   'virtualenv-{}.tar.gz'.format(self.version))
            print('Downloading virtualenv')
            tarball = os.path.join(directory, 'virtualenv.tar.gz')
            with contextlib.closing(self._fetch(url)) as response:
                with open(tarball, 'wb') as file:
                    shutil.copyfileobj(response, file)
            with contextlib.closing(tarfile.open(tarball, 'r|gz')) as archive:
                archive.extractall(directory)

        def create(self, directory):
            tmpdir = tempfile.mkdtemp()
            try:
                self.download(tmpdir)
                args = [sys.executable]
                args.append(os.path.join(tmpdir,
                        'virtualenv-{}'.format(self.version), 'virtualenv.py'))
                if self.prompt:
                    args.extend(['--prompt', prompt])
                args.append(directory)
                subprocess.check_call(args)
                if sys.platform == 'win32':
                    self.env_exe = os.path.join(directory, 'scripts', 'python.exe')
                else:
                    self.env_exe = os.path.join(directory, 'bin', 'python')
                assert(os.path.exists(self.env_exe))
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

    # Install the virtual environment.
    builder = EnvBuilder(prompt=prompt)
    builder.create(directory)
    # Run this script within the virtual environment for stage2
    subprocess.check_call([builder.env_exe, __file__])


def split_requirement(req):
    for i, c in enumerate(req):
        if not c.isalnum() and c not in '.-_':
            return req[:i].lower(), req
    return req.lower(), req


def stage2(directory=_path):
    from setup import install_requires
    requirements = dict(split_requirement(req) for req in install_requires)
    requirements_txt = os.path.join(_path, 'requirements.txt')
    if os.path.exists(requirements_txt):
        with open(requirements_txt) as file:
            requirements.update(
                    dict(split_requirement(req.rstrip()) for req in file))
    # Install packages provided only as eggs
    args = [sys.executable, '-m', 'easy_install']
    for name in ['bacpypes']:
        args.append(requirements.get(name, name))
    print(' '.join(args))
    subprocess.check_call(args)
    # Install local packages and remaining dependencies
    args = [sys.executable, '-m', 'pip', 'install',
            '--global-option', '-q',
            '-e', os.path.join(directory, 'lib', 'jsonrpc'),
            '-e', os.path.join(directory, 'lib', 'clock'),
            '-e', directory]
    if os.path.exists(requirements_txt):
        args.extend(['-r', requirements_txt])
    print(' '.join(args))
    subprocess.check_call(args)


def main(directory=_envdir, prompt=_prompt):
    # Unfortunately, many dependencies are not yet available in Python3.
    if sys.version_info[:2] != (2, 7):
        sys.stderr.write('error: Python 2.7 is required\n')
        sys.exit(1)
    if hasattr(sys, 'real_prefix'):
        stage2()
    else:
        stage1()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
