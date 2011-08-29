#!/usr/bin/env python

import os, sys
import fnmatch
import getopt
import hashlib
import math
import logging
import random
import json
import stat
import subprocess
import time
import uuid

_log = logging.getLogger('photostream')

###########################################################################
# Utilities.
###########################################################################

def numdigits(n):
    """
    Return digit count for number ``n`` (n=0 is counted as 1).
    """
    return 1 if (n == 0) else int(math.floor(math.log10(n)) + 1)

def filesystem_encode(s):
    """
    Return unicode string ``s`` encoded using the underlying filesystem codec.
    """
    return s.encode(sys.getfilesystemencoding())


def calc_sha256(filepath):
    """
    Get SHA256 hash for ``filepath``, returns digest as string in hex format.
    """
    sha256 = hashlib.sha256()
    sha256.update(open(filepath, "rb").read())
    return sha256.hexdigest()


def rmfile(filename, retry=10):
    """
    Delete ``filename`` handling read-only issues correctly. If errors occur
    we'll retry a maximum of ``retry`` counts.
    """
    try:
        if os.path.isfile(filename):
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        if os.path.exists(filename):
            raise IOError("Failed to delete: %s" % filename)
    except (IOError, WindowsError):
        if retry:
            time.sleep(1)
            rmfile(filename, retry-1)
        else:
            raise

def read_exif(filepaths):
    """
    Read EXIF data for ``filepaths`` and return a dict mapping filesnames with
    with key/value pairs for the EXIF properties (see exiftool docs for details).

    Example:
      read_exif(['a.jpg', 'b.jpg']) -> {'a.jpg': {key:value, ...},
                                        'b.jpg': {key:value, ...}}
    """
    opts = ["-j", # export to json format
            "-n", # write values as numbers instead words
            "-q", # quiet processing, supress information messages
            "-s", # print tag names instead of descriptions
    ]
    try:
        args = ["exiftool"] + opts + filepaths
        args = [filesystem_encode(a) for a in args]
        (stdout, stderr) = subprocess.Popen(args, stdout=subprocess.PIPE).communicate()
        # Exif data is returned as an array of hashtables by exiftool, we'll
        # manually map filenames to EXIF data to make it easier to work with.
        data = {}
        for item in json.loads(stdout.decode('latin-1')):
            data[item["SourceFile"]] = item
        return data
    except IOError:
        return {}


def list_photos(path):
    """
    Return list of *.jpg in ``dirpath``.
    """
    files = []
    for filename in sorted(os.listdir(path)):
        filepath = os.path.join(path, filename)
        if not os.path.isfile(filepath):
            continue
        if fnmatch.fnmatch(filepath, "*.jpg"):
            files.append(filepath)
    return files


###########################################################################
# Organize photostream.
###########################################################################

def organize_photos(path, unique=False, randomize=False):
    """
    Organize *.jpg in ``path`` by renaming them using a schema like 001.jpg,
    002.jpg (prefix modified to suit the size of the photo collection) sorted
    by their creation date (override by setting ``randomize`` to True). If
    ``unique`` is True duplicate photos will be deleted.
    """
    filemap = {} # map SHA-256 -> (filepath, timestamp)
    for (filepath, props) in read_exif(list_photos(path)).iteritems():
        signature = calc_sha256(filepath)
        if signature in filemap:
            _log.info("Deleting duplicate image: %s" % filepath)
            rmfile(filepath)
        else:
            tmp_filepath = os.path.join(path, "%s.work.jpg" % signature)
            if filepath != tmp_filepath:
                if os.path.isfile(tmp_filepath):
                    rmfile(tmp_filepath)
                os.rename(filepath, tmp_filepath)
            timestamp = props["CreateDate"] if (randomize == False) else random.random()
            filemap[signature] = (tmp_filepath, timestamp)

    files = [filepath for (filepath, timestamp) in
             sorted(filemap.values(), key=lambda (filepath, timestamp): timestamp)]

    fmt_str = "%0" + str(numdigits(len(files))) + "d.jpg"

    for (n, filepath) in enumerate(files):
        new_filepath = os.path.join(os.path.split(filepath)[0], fmt_str % (n+1))
        os.rename(filepath, new_filepath)


def usage(errmsg=None):
    """
    Output usage instruction or ``errmsg`` and exit process.
    """
    if errmsg:
        print "photostream:", errmsg
        print
    print "Usage: photostream [OPTIONS] [DIRS] ...                        "
    print "Options:                                                       "
    print "  -u           filter unique photos and delete duplicates      "
    print "  -r           randomize order instead of sorting by timestamp "
    print "  -h           show this help message                          "
    print
    sys.exit(-1)



def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], "urh")
    except getopt.GetoptError, e:
        usage(e)

    if len(args) < 1:
        usage("missing input directory")

    unique, randomize = (False, False)

    for (o, a) in opts:
        if o == "-u":
            unique = True
        elif o == "-r":
            randomize = True
        elif o == "-h":
            usage()
        else:
            assert(0)

    for path in args:
        organize_photos(os.path.abspath(path), unique, randomize)


###########################################################################
# Program entry-point.
###########################################################################

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())
    main(sys.argv)


###########################################################################
# The End.
###########################################################################
