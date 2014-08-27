import base64
from collections import Iterable
from contextlib import closing
import csv
import errno
import hashlib
import logging
import os
import posixpath
import re
import shutil
import StringIO
import sys
import time
import uuid
import wheel
import tempfile
import zipfile

try:
    import simplejson as jsonapi
except ImportError:
    import json as jsonapi

from wheel.install import WheelFile
from wheel.tool import unpack
from wheel.util import (native,
                        open_for_csv,
                        urlsafe_b64decode)
from volttron.platform import config


__all__ = ('BasePackageVerifier', 'VolttronPackageWheelFileNoSign',
           'ZipPackageVerifier', 'UnpackedPackage')

_log = logging.getLogger(__name__)

#TODO: Make this this base class and have auth extend it
class VolttronPackageWheelFileNoSign(WheelFile):
    AGENT_DATA_ZIP = 'agent_data.zip'

    def __init__(self,
                 filename,**kwargs):

        super(VolttronPackageWheelFileNoSign, self).__init__(filename, **kwargs)

    @property
    def agent_data_dir(self):
        return "%s.agent-data" % self.parsed_filename.group('namever')

    @property
    def agent_data_name(self):
        return "%s/%s" % (self.agent_data_dir, self.AGENT_DATA_ZIP)

    @property
    def ready_to_move(self):
        return True


    def contains(self, path):
        '''Does the wheel contain the specified path?'''

        for x in self.zipfile.filelist:
            if x.filename == path:
                return True
        return False

    def add_agent_data(self, agent_dir):
        '''Adds the agent's data to the wheel file

        agent_dir is the root for an installed agent.
        '''
        try:
            tmpdir = tempfile.mkdtemp()
            abs_agent_dir = os.path.join(agent_dir, self.agent_data_dir)
            zipFilename = os.path.join(tmpdir, 'tmp')
            zipFilename = shutil.make_archive(zipFilename, "zip",
                                              abs_agent_dir)
            self.zipfile.write(zipFilename, self.agent_data_name)
            self.__setupzipfile__()
        finally:
            shutil.rmtree(tmpdir, True)

    def add_files(self, files_to_add=None, basedir='.'):

        if files_to_add == None or len(files_to_add) == 0:
            return

        records = ZipPackageVerifier(self.filename).get_records()

        if (len(records) < 1):
            raise ValueError('Invalid wheel file no records found')

        last_record_name = records[-1]
#         new_record_name = "RECORD.{}".format(len(records))
# 
        tmp_dir = tempfile.mkdtemp()
        record_path = '/'.join((self.distinfo_name, last_record_name))
        tmp_new_record_file = '/'.join((tmp_dir, self.distinfo_name, last_record_name))
        self.zipfile.extract('/'.join((self.distinfo_name, last_record_name)), path = tmp_dir)
        
        self.remove_files('/'.join((self.distinfo_name, 'config')))
        
        with closing(open_for_csv(tmp_new_record_file,"a+")) as record_file:
            writer = csv.writer(record_file)


            if files_to_add:
                if 'config_file' in files_to_add.keys():
                    try:
                        data = open(files_to_add['config_file']).read()
                    except Exception as e:
                        _log.error("couldn't access {}" % files_to_add['config_file'])
                        raise
    
                    if files_to_add['config_file'] != 'config':
                        msg = 'WARNING: renaming passed config file: {}'.format(
                                                    files_to_add['config_file'])
                        msg += ' to config'
                        sys.stderr.write(msg)
                        _log.warn(msg)
    
                    self.zipfile.writestr("%s/%s" % (self.distinfo_name, 'config'),
                                          data)
                    
                    (hash_data, size, digest) = self._record_digest(data)
                    record_path = '/'.join((self.distinfo_name, 'config'))
                    writer.writerow((record_path, hash_data, size))
                    
                if 'contract' in files_to_add.keys() and files_to_add['contract'] is not None:
                    try:
                        data = open(files_to_add['contract']).read()
                    except Exception as e:
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

    def pop_records_file(self):
        '''Pop off the last records file that was added'''
        records = ZipPackageVerifier(self.filename).get_records()
        topop = (os.path.join(self.distinfo_name, records[0]),)
        self.remove_files(topop)

        

    def remove_files(self, files):
        '''Relative to files in the package, ie: ./dist-info/config
        '''
        if not isinstance(files, Iterable):
            files = [files]
        tmpdir = tempfile.mkdtemp()
        zipFilename = os.path.join(tmpdir, 'tmp.zip')
        newZip = zipfile.ZipFile(zipFilename, 'w')

        for f in self.zipfile.infolist():
            if f.filename not in files:
                buf = self.zipfile.read(f.filename)
                newZip.writestr(f.filename, buf)
        newZip.close()
        self.zipfile.close()
        self.fp = None
        os.remove(self.filename)
        shutil.move(zipFilename, self.filename)
        self.__setupzipfile__()



    def unpack(self, dest='.'):
        namever = self.parsed_filename.group('namever')
        destination = os.path.join(dest, namever)
        sys.stderr.write("Unpacking to: %s\n" % (destination))
        self.zipfile.extractall(destination)
        self.zipfile.close()

        data_dir = os.path.join(dest, self.agent_data_dir)
        data_file = os.path.join(dest, self.agent_data_name)
        if not os.path.isdir(data_dir):
            _log.debug("no agent_data creating agent data directory")
            os.mkdir(data_dir)
            return
        
        if not os.path.isfile(data_file):
            _log.debug("no agent_data.zip")
            return
        
        _log.debug("extracting agent_data")
        zip = zipfile.ZipFile(data_file)
        zip.extractall(self.agent_data_name)
        zip.close()
        os.remove(data_file)

    def _record_digest(self, data):
        '''Returns a three tuple of hash, size and digest.'''

        from wheel.util import urlsafe_b64encode

        digest = hashlib.sha256(data).digest()
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

#     def verify(self):
#         '''Verify the hashes of every file in the RECORD files of the package.
# 
#         if a problem exists AuthError is raised
#         '''
#         for record in self.get_records():
#             # only if the function exists will we look for the smime
#             # signature.
#             if getattr(self, 'verify_smime_signature', None) is not None:
#                 try:
#                     if not self.verify_smime_signature(record):
#                         path = posixpath.join(self.dist_info, record)
#                         msg = '{}: failed signature verification'.format(path)
#                         _log.debug(msg)
#                         raise AuthError(msg)
#                 except KeyError as e:
#                     path = posixpath.join(self.dist_info, record)
#                     msg = '{}: failed signature verification'.format(path)
#                     _log.debug(msg)
#                     raise AuthError(msg)
#             for path, hash, expected_hash in self.iter_hashes(record):
#                 if not expected_hash:
#                     _log.warning('{}: no hash for file'.format(path))
#                 elif hash != expected_hash:
#                     msg = '{}: failed hash verification'.format(path)
#                     _log.error(msg)
#                     _log.debug('{}: hashes are not equal: computed={}, expected={}'.format(
#                             path, hash, expected_hash))
#                     raise AuthError(msg)
                
                
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

    def verify_smime_signature(self, name='RECORD'):
        '''Verify the S/MIME (.p7s) signature of named RECORD file.'''
        record = posixpath.join(self.dist_info, name)
        record_p7s = record + '.p7s'


        content = StringIO.StringIO()
        content.write(self._zipfile.read(record_p7s))
        content.seek(0)
        return self._certsobj.verify_smime(content)

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

    def get_metadata(self):
        with open(os.path.join(self.distinfo, 'metadata.json')) as file:
            return jsonapi.load(file)

    def _read_metadata(self):
        metadata = self.get_metadata()
        self._name = metadata['name']
        self._version = metadata['version']

    def get_wheelmeta(self):
        with open(os.path.join(self.distinfo, 'WHEEL')) as file:
            return {key.strip().lower(): value.strip()
                    for key, value in
                    (parts for line in file if line
                     for parts in [line.split(':', 1)] if len(parts) == 2)}

    def _read_wheelmeta(self):
        meta = self.get_wheelmeta()
        self._tag = meta['tag']

    @property
    def name(self):
        try:
            return self._name
        except AttributeError:
            pass
        self._read_metadata()
        return self._name
    
    @property
    def version(self):
        try:
            return self._version
        except AttributeError:
            pass
        self._read_metadata()
        return self._version
    
    @property
    def tag(self):
        try:
            return self._tag
        except AttributeError:
            pass
        self._read_wheelmeta()
        return self._tag
    
    @property
    def package_name(self):
        return '-'.join([self.name, self.version])
    
    @property
    def wheel_name(self):
        return '-'.join([self.name, self.version, self.tag]) + '.whl'

    def repack(self, dest=None, exclude=None):
        records = [name for name in os.listdir(self.distinfo)
                   if _record_re.match(name)]
        records.sort()
        wheelname = self.wheel_name
        if dest is not None:
            dest = os.path.expanduser(os.path.expandvars(dest))
            wheelname = os.path.join(dest, wheelname)
        with zipfile.ZipFile(wheelname, 'w') as wheelfile:
            try:
                for record in records:
                    if exclude and record in exclude:
                        continue
                    with open(os.path.join(self.distinfo, record)) as file:
                        csvfile = csv.reader(file)
                        for row in csvfile:
                            name = row[0]
                            wheelfile.write(os.path.join(self.directory, name), name)
            except Exception:
                wheelfile.close()
                os.unlink(wheelfile.filename)
                raise
        return wheelfile.filename
