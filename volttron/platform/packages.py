# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import base64
from contextlib import closing
import csv
import hashlib
import logging
import os
import posixpath
import re
import shutil
import sys
import tempfile
import zipfile

from volttron.platform import jsonapi

from wheel.install import WheelFile
from wheel.util import native, open_for_csv


__all__ = ('BasePackageVerifier', 'VolttronPackageWheelFileNoSign',
           'ZipPackageVerifier', 'UnpackedPackage')

_log = logging.getLogger(__name__)

#TODO: Make this this base class and have auth extend it
class VolttronPackageWheelFileNoSign(WheelFile):
    AGENT_DATA_ZIP = 'agent_data.zip'

    def __init__(self,
                 filename,**kwargs):

        super(VolttronPackageWheelFileNoSign, self).__init__(filename, 
                                                             **kwargs)

    def contains(self, path):
        '''Does the wheel contain the specified path?'''

        for x in self.zipfile.filelist:
            if x.filename == path:
                return True
        return False

    def add_files(self, files_to_add=None, basedir='.'):

        if files_to_add == None or len(files_to_add) == 0:
            return

        records = ZipPackageVerifier(self.filename).get_records()

        if (len(records) < 1):
            raise ValueError('Invalid wheel file no records found')

        last_record_name = records[0]
#         new_record_name = "RECORD.{}".format(len(records))
# 
        tmp_dir = tempfile.mkdtemp()
        try:
            record_path = '/'.join((self.distinfo_name, last_record_name))
            tmp_new_record_file = '/'.join((tmp_dir, self.distinfo_name, 
                                            last_record_name))
            self.zipfile.extract('/'.join((self.distinfo_name, last_record_name)), 
                                 path = tmp_dir)

            self.remove_files('/'.join((self.distinfo_name, 'config')))

            with closing(open_for_csv(tmp_new_record_file,"a+")) as record_file:
                writer = csv.writer(record_file)


                if files_to_add:
                    if 'config_file' in files_to_add:
                        try:
                            data = open(files_to_add['config_file']).read()
                        except OSError as e:
                            _log.error("couldn't access {}" % files_to_add['config_file'])
                            raise

                        self.zipfile.writestr("%s/%s" % (self.distinfo_name, 'config'),
                                              data)

                        (hash_data, size, digest) = self._record_digest(data)
                        record_path = '/'.join((self.distinfo_name, 'config'))
                        writer.writerow((record_path, hash_data, size))

                    if 'identity_file' in files_to_add:
                        try:
                            data = open(files_to_add['identity_file']).read()
                        except OSError as e:
                            _log.error("couldn't access {}" % files_to_add['identity_file'])
                            raise

                        self.zipfile.writestr("%s/%s" % (self.distinfo_name, 'IDENTITY_TEMPLATE'),
                                              data)

                        (hash_data, size, digest) = self._record_digest(data)
                        record_path = '/'.join((self.distinfo_name, 'IDENTITY_TEMPLATE'))
                        writer.writerow((record_path, hash_data, size))

                    if 'contract' in files_to_add and files_to_add['contract'] is not None:
                        try:
                            data = open(files_to_add['contract']).read()
                        except OSError as e:
                            _log.error("couldn't access {}" % files_to_add['contract'])
                            raise

                        if files_to_add['contract'] != 'execreqs.json':
                            msg = 'WARNING: renaming passed contract file: {}'.format(
                                                        files_to_add['contract'])
                            msg += ' to execreqs.json'
                            sys.stderr.write(msg)
                            _log.warn(msg)

                        self.zipfile.writestr("%s/%s" % (self.distinfo_name, 'execreqs.json'),
                                              data)
                        (hash_data, size, digest) = self._record_digest(data)
                        record_path = '/'.join((self.distinfo_name, 'execreqs.json'))
                        writer.writerow((record_path, hash_data, size))


                    self.__setupzipfile__()

            self.pop_records_file()

            new_record_content = open(tmp_new_record_file, 'r').read()
            self.zipfile.writestr(self.distinfo_name+"/"+last_record_name,
                    new_record_content)

            self.zipfile.close()
            self.__setupzipfile__()
        finally:
            shutil.rmtree(tmp_dir, True)

    def pop_records_file(self):
        '''Pop off the last records file that was added'''
        records = ZipPackageVerifier(self.filename).get_records()
        topop = (os.path.join(self.distinfo_name, records[0]),)
        self.remove_files(topop)

    def pop_record_and_files(self):
        '''Pop off the last record file and files listed in it.

        Only removes files that are not listed in remaining records.
        '''
        records = ZipPackageVerifier(self.filename).get_records()
        record = records.pop(0)
        zf = self.zipfile
        keep = set(row[0] for name in records for row in
            csv.reader(zf.open(posixpath.join(self.distinfo_name, name))))
        drop = set(row[0] for row in
            csv.reader(zf.open(posixpath.join(self.distinfo_name, record))))
        # These two should already be listed, but add them just in case
        drop.add(posixpath.join(self.distinfo_name, record))
        self.remove_files(drop - keep)

    def remove_files(self, files):
        '''Relative to files in the package, ie: ./dist-info/config.'''
        if isinstance(files, str):
            files = [files]
        tmpdir = tempfile.mkdtemp()
        try:
            newzip = zipfile.ZipFile(os.path.join(tmpdir, 'tmp.zip'), 'w')
            with newzip:
                for f in self.zipfile.infolist():
                    if f.filename not in files:
                        buf = self.zipfile.read(f.filename)
                        newzip.writestr(f.filename, buf)
            self.zipfile.close()
            self.fp = None
            os.remove(self.filename)
            shutil.move(newzip.filename, self.filename)
            self.__setupzipfile__()
        finally:
            shutil.rmtree(tmpdir, True)

    def unpack(self, dest='.'):
        namever = self.parsed_filename.group('namever')
        destination = os.path.join(dest, namever)
        sys.stderr.write("Unpacking to: %s\n" % (destination))
        self.zipfile.extractall(destination)
        self.zipfile.close()

    def _record_digest(self, data):
        '''Returns a three tuple of hash, size and digest.'''

        from wheel.util import urlsafe_b64encode

        digest = hashlib.sha256(data.encode("utf-8")).digest()
        hash_text = 'sha256=' + native(urlsafe_b64encode(digest))
        size = len(data)
        return (hash_text, size, digest)

    def __setupzipfile__(self):
        self.zipfile.close()
        self.fp = None

        mode = 'r'
        if self.append:
            mode = 'a'

        self.zipfile = zipfile.ZipFile(self.filename,
                                               mode=mode,
                              )


_record_re = re.compile(r'^RECORD(?:\.\d+)?$')
_all_record_re = re.compile(r'^(?:.*/)?RECORD(?:\.\d+)?(?:\.p7s)?$')


#
# Signature verification in the class below has the limitation that only
# a single certificate may be used for verification. Ideally, the
# certificate should be extracted from the signature file and verified
# against a certificate authority (CA) in the CA store. See
# http://code.activestate.com/recipes/285211/ for an alternate solution
# using M2Crypto.
#
class BasePackageVerifier(object):
    '''Base class for implementing wheel package verification.

    Verifies wheel packages as defined in PEP-427. May be inherited with
    minimal modifications to support different storage mechanisms, such
    as a filesystem, Zip file, or tarball. All paths are expected to be
    POSIX-style with forward-slashes. Subclasses should implement
    listdir and open and may override __init__, if needed.

    As an extension of the original specification, multiple levels of
    RECORD files and signatures are supported by appending incrementing
    integers to the RECORD files. Verification happens in reverse order
    and later RECORD files should contain hashes of the previous RECORD
    and associated signature file(s).
    '''

    def __init__(self, dist_info, **kwargs):
        '''Initialize the instance with the dist-info directory name.

        dist_info should contain the name of a single directory, not a
        multi-component path.
        '''
        self.dist_info = dist_info



    def listdir(self, path):
        '''Return a possibly empty list of files from a directory.

        This could return the contents of a directory in an archive or
        whatever makes sense for the storage mechanism. Paths will
        typically be relative to the package, however, for installed
        packages, absolute paths are possible.
        '''
        raise NotImplementedError()

    def open(self, path, mode='r'):
        '''Return a file-like object for the given file.

        mode is interpreted the same as for the built-in open and will
        be either 'r' or 'rb'. Only the __iter__(), read(), and close()
        methods are used.
        '''
        raise NotImplementedError()

    def iter_hashes(self, name='RECORD'):
        '''Iterate over the files and hashes of a RECORD file.

        The RECORD file with the given name will be iterated over
        yielding a three tuple with each iteration: filename (relative
        to the package), computed hash (just calculated), and expected
        hash (from RECORD file).
        '''
        hashless = [posixpath.join(self.dist_info, name + ext)
                    for ext in ['', '.jws', '.p7s']]
        path = posixpath.join(self.dist_info, name)
        with closing(self.open(path)) as record_file:
            for row in csv.reader(record_file):
                filename, hashspec = row[:2]
                if not hashspec:
                    if filename not in hashless:
                        yield filename, None, None
                    continue
                algo, expected_hash = hashspec.split('=', 1)
                hash = hashlib.new(algo)
                with closing(self.open(filename, 'rb')) as file:
                    while True:
                        data = file.read(4096)
                        if not data:
                            break
                        hash.update(data)
                hash = base64.urlsafe_b64encode(hash.digest()).rstrip('=')
                yield filename, hash, expected_hash

    def get_records(self):
        '''Return a reverse sorted list of RECORD names from the package.

        Returns all RECORD files in the dist_info directory.
        '''
        records = [name for name in self.listdir(self.dist_info)
                   if _record_re.match(name)]
        records.sort(key=lambda x: int((x.split('.', 1) + [-1])[1]), reverse=True)
        if not records:
            raise ValueError('missing RECORD file(s) in .dist-info directory')
        return records

                
class ZipPackageVerifier(BasePackageVerifier):
    '''Verify files of a Zip file.'''

    def __init__(self, zip_path, mode='r', **kwargs):
        self._zipfile = zipfile.ZipFile(zip_path)
        self._namelist = self._zipfile.namelist()

        names = [name for name in self._namelist
                 if name.endswith('.dist-info/RECORD') and name.count('/') == 1]
        if len(names) != 1:
            raise ValueError('unable to determine dist-info directory')
        dist_info = names[0].split('/', 1)[0]
        super(ZipPackageVerifier, self).__init__(dist_info, **kwargs)

    def listdir(self, path):
        if path[-1:] != '/':
            path += '/'
        n = len(path)
        return [name[n:].split('/', 1)[0]
                for name in self._namelist if name.startswith(path)]

    def open(self, path, mode='r'):
        return self._zipfile.open(path, 'r')


class UnpackedPackage(object):
    '''Represents an package unpacked into a directory.

    Allows one access to the package metadata and methods to repack.
    '''

    def __init__(self, base_directory):
        self.directory = base_directory
        self.distinfo = self._get_dist_info()

    def _get_dist_info(self):
        '''Find the package.dist-info directory.'''
        basename = os.path.basename(self.directory)
        path = os.path.join(self.directory, basename + '.dist-info')
        if os.path.exists(path):
            return path
        for name in os.listdir(self.directory):
            if not name.endswith('.dist-info'):
                continue
            return os.path.join(self.directory, name)
        raise ValueError('directory does not contain a valid '
                         'agent package: {}'.format(self.directory))

    @property
    def metadata(self):
        '''Parse package.dist-info/metadata.json and return a dictionary.'''
        try:
            return self._metadata
        except AttributeError:
            with open(os.path.join(self.distinfo, 'metadata.json')) as file:
                self._metadata = jsonapi.load(file)
        return self._metadata

    @property
    def wheelmeta(self):
        '''Parse package.dist-info/WHEEL and return a dictionary.'''
        try:
            return self._wheelmeta
        except AttributeError:
            with open(os.path.join(self.distinfo, 'WHEEL')) as file:
                self._wheelmeta = {
                    key.strip().lower(): value.strip()
                    for key, value in
                    (parts for line in file if line
                    for parts in [line.split(':', 1)] if len(parts) == 2)
                }
        return self._wheelmeta

    @property
    def package_name(self):
        metadata = self.metadata
        name = metadata['name']
        version = metadata['version']
        return '-'.join([name, version])

    @property
    def version(self):
        metadata = self.metadata
        return metadata['version']
    
    @property
    def wheel_name(self):
        metadata = self.metadata
        name = metadata['name']
        version = metadata['version']
        tag = self.wheelmeta['tag']
        return '-'.join([name, version, tag]) + '.whl'

    def repack(self, dest=None, exclude=None):
        '''Recreate the package from the RECORD files.

        Put the package in the directory given by dest or in the current
        directory if dest is None. If exclude is given, do not add files
        for RECORD files in exclude. Returns the path to the new package.
        '''
        # Get a list of the record files and sort them ascending
        records = [name for name in os.listdir(self.distinfo)
                   if _record_re.match(name)]
        records.sort()
        wheelname = self.wheel_name
        if dest is not None:
            dest = os.path.expanduser(os.path.expandvars(dest))
            wheelname = os.path.join(dest, wheelname)
        # Recreate the package
        with zipfile.ZipFile(wheelname, 'w') as wheelfile:
            for record in records:
                # Exclude and record files in exclude
                if exclude and record in exclude:
                    continue
                with open(os.path.join(self.distinfo, record)) as file:
                    csvfile = csv.reader(file)
                    for row in csvfile:
                        name = row[0]
                        # Skip already added RECORD files or signatures
                        if (_all_record_re.match(name) and
                                name in wheelfile.namelist()):
                            continue
                        wheelfile.write(os.path.join(self.directory, name), name)
        return wheelfile.filename
