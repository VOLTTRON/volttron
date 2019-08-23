import os
import shutil
import subprocess
import urllib2


def installmongo():
    mongofileroot = "mongodb-linux-x86_64-3.2.8"
    mongofile = "{}.tgz".format(mongofileroot)
    mongodir = "mongodb"
    if os.path.exists(mongofile):
        os.remove(mongofile)
    if os.path.exists(mongodir):
        shutil.rmtree(mongodir)

    version_url = "https://fastdl.mongodb.org/linux/{}".format(mongofile)
    f = urllib2.urlopen(version_url)
    data = f.read()
    with open(mongofile, "wb") as img_file:
        img_file.write(data)
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