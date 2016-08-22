import os
import shutil
import subprocess


def installmongo():
    mongofileroot = "mongodb-linux-x86_64-3.2.8"
    mongofile = "{}.tgz".format(mongofileroot)
    mongodir = "mongodb"
    if os.path.exists(mongofile):
        os.remove(mongofile)
    if os.path.exists(mongodir):
        shutil.rmtree(mongodir)

    version_url = "https://fastdl.mongodb.org/linux/{}".format(mongofile)
    local_filename = version_url.split('/')[-1]

    cmd = ['wget', version_url]
    ret = subprocess.check_call(cmd)
    cmd = ['tar', '-zxvf', mongofile]
    ret = subprocess.check_call(cmd)
    cmd = ['mkdir', '-p', 'mongodb']
    ret = subprocess.check_call(cmd)
    cmd = ['cp', '-R', '-n', '{}/'.format(mongofileroot), mongodir]
    ret = subprocess.check_call(cmd)
    print(ret)


def main():
    installmongo()

if __name__ == '__main__':
    main()