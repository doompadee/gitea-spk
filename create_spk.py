#!/usr/bin/env python

import argparse
import collections
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib
import urllib2


DIR = os.path.dirname(os.path.realpath(sys.argv[0]))

Version = collections.namedtuple('Version', ['tag', 'number', 'beta'])


def _show_progress(count, block_size, total_size):
    if total_size < 0:
        return
    global start_time
    if count == 0:
        start_time = time.time()
        return
    duration = time.time() - start_time
    progress_size = int(count * block_size)
    speed = int(progress_size / (1024 * duration))
    percent = int(count * block_size * 100 / total_size)
    sys.stdout.write("\r    %d%%, %d MB, %d KB/s, %d seconds" % (percent, progress_size / (1024 * 1024), speed, duration))
    if count * block_size >= total_size:
        sys.stdout.write(u'\u001b[2K\u001b[0G')
    sys.stdout.flush()


def _get_package_arch():
    """ Determines the package arch when running on a DiskStation.
    """
    info = subprocess.check_output(['uname', '-a']).strip()

    match = re.search('synology_(.*)_.*$', info)
    if match:
        return match.group(1)
    else:
        _fail('Could not determine package arch from system info: "%s". Either use -a,--arch or -p,--platform to specify Synology package arch or Gitea platform' % info)


def _get_mappings():
    """ Returns the mappings from Gitea platform to Synology package archs.
    """
    global mappings
    if 'mappings' in globals():
        return mappings
    mappings = {}
    with open('%s/arch.desc' % DIR) as f:
        for line in f.readlines():
            line = line.strip();
            # ignore comments
            if line.startswith('#'):
                continue
            mapping = line.split(' ', 1)
            mappings[mapping[0]] = mapping[1]
    return mappings


def _get_platform(arch=None, binary=None):
    """ Returns the Gitea platform for the given Synology package arch
        or Gitea binary.
    """
    if binary:
        result = re.match('.*?-.*?(?:-rc[0-9]+)?-.*?-(.*)', os.path.basename(binary))
        if result:
            return result.group(1)
        else:
            _fail('Could not determine platform: "%s"' % binary)

    m = _get_mappings()

    # ensure that provided string is at least as long as the smallest valid arch
    # package to prevent partial string matches as much as possible
    if len(arch) < len(min([a for archs in m.values() for a in archs.split(' ')], key=len)):
        _fail('Invalid package arch "%s". Valid archs are: %s' % (arch, _get_archs()))

    for platform in m:
        if arch in m[platform]:
            return platform

    _fail('Unknown package arch "%s". Valid archs are: %s' % (arch, _get_archs()))


def _get_platforms():
    """ Returns the valid Gitea platform values.
    """
    return ', '.join(['%s' % k for k in sorted(_get_mappings().keys())])


def _get_arch(platform):
    """ Returns the Synology package arch for the given Gitea platform.
    """
    m = _get_mappings()
    if platform in m:
        return m[platform]

    _fail('Unknown platform "%s". Valid platforms are: %s' % (platform, _get_platforms()))


def _get_archs():
    """ Returns the valid Synology package arch values.
    """
    return ', '.join(['%s' %  a for archs in _get_mappings().values() for a in archs.split(' ')])


def _get_version(binary):
    """ Returns version number of the given Gitea binary.
    """
    name = os.path.basename(binary)
    result = re.search('([0-9]\.[0-9]\.[0-9](-rc[0-9]+)?)', name)
    if result:
        return Version(tag='v%s' % result.group(1), number=result.group(1), beta=True if result.group(2) else False)
    _fail('Could not determine version "%s"' % binary)


def _get_latest_version():
    """ Determines the latest Gitea release version.
    """
    print('Determine latest version...')
    url = 'https://api.github.com/repos/go-gitea/gitea/releases/latest'
    response = urllib2.urlopen(url)

    if response.getcode() != 200:
        _fail('Could not determine latest version')

    content = response.read().decode('utf-8')
    data = json.loads(content)

    return Version(tag=data['tag_name'], number=data['tag_name'].replace('v', ''), beta=False), data['body'] if 'body' in data else ''


def _get_changelog(version):
    """ Determines the changelog for the given Gitea version.
    """
    url = 'https://api.github.com/repos/go-gitea/gitea/releases/tags/%s'% version.tag 
    response = urllib2.urlopen(url)

    if response.getcode() != 200:
        _fail('Could not determine changelog for %s ' % version.tag)

    string = response.read().decode('utf-8')
    data = json.loads(string)

    return data['body'] if 'body' in data else 'NOT FOUND'


def _get_filename(version, platform):
    """ Returns the Gitea file name for the given version/platform.
    """
    return 'gitea-%s-%s' % (version.number, {
        'amd64': 'linux-amd64',
        'arm-5': 'linux-arm-5',
        'arm-7': 'linux-arm-7',
        'arm64': 'linux-arm64'
    }.get(platform))


def _update_metadata(version, arch, changelog):
    """ Updates the package metadata to reflect the binary being build.
    """
    file_name = '%s/2_create_project/INFO' % DIR
    shutil.copy('%s.in' % file_name, file_name)
    with open(file_name, 'r+') as f:
        contents = f.read()
        contents = re.sub('version=".*?"', 'version="%s"' % version.number, contents)
        contents = re.sub('arch=".*?"', 'arch="%s"' % arch, contents)
        contents = re.sub('beta=".*?"', 'beta="%s"' % ('yes' if version.beta else 'no'), contents)
        contents = re.sub('changelog=".*?"', 'changelog="%s"' % changelog, contents)
        f.seek(0)
        f.write(contents)


def _make_executable(file_name):
    os.chmod(file_name, os.stat(file_name).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _download(url, file_name):
    f = '%s/%s' % (DIR, file_name)
    if not os.path.isfile(f):
        print('Downloading %s...' % file_name)
        fname, response = urllib.urlretrieve(url, f, _show_progress)
        if response.get('status') == '404 Not Found':
            os.remove(fname)
            _fail('%s no valid Gitea release' % file_name)
        _make_executable(file_name)
    return f


def _fail(message):
    #subprocess.call(['synologset1', 'sys', 'err', '0x11800000', message])
    sys.exit(message)


def _target_directory(dir):
    return dir if dir else DIR


def _create_package(version, arch, platform, changelog, force, directory):
    """ Creates the Gitea package.
    """
    file_name = _get_filename(version, platform)
    package_name = '%s/%s.spk' % (directory, file_name)

    if not force and os.path.isfile(package_name):
        print('%s already exists' % package_name)
        return

    print('Building Gitea %s for %s...' % (version.number, arch))

    url = 'https://github.com/go-gitea/gitea/releases/download/%s/%s' % (version.tag, file_name)
    binary = _download(url, file_name)

    print('Creating package %s...' % package_name)

    _update_metadata(version, arch, changelog)

    app_dir = '%s/1_create_package/gitea' % DIR
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)

    bin_link = '%s/gitea' % app_dir
    if os.path.lexists(bin_link):
        os.remove(bin_link)
    os.symlink(binary, bin_link)

    pkg = '%s/2_create_project/package.tgz' % DIR

    with tarfile.open(pkg, mode='w:gz', dereference=True) as archive:
        archive.add('%s/1_create_package' % DIR, arcname='', recursive=True)

    with tarfile.open(package_name, mode='w:gz') as archive:
        archive.add('%s/2_create_project' % DIR, arcname='', recursive=True, filter=lambda x: None if x.name.endswith('INFO.in') else x)

    os.remove(pkg)


def _parse_args():
    parser = argparse.ArgumentParser(description='Create Gitea Synology package')
    group = parser.add_mutually_exclusive_group()
    parser.add_argument('binaries', metavar='FILE', nargs='*', help='a Gitea binary')
    group.add_argument('-a', '--arch', help='create package for the given Synology package arch')
    parser.add_argument('-d', '--directory', metavar='DIR', help='store packages in directory')
    parser.add_argument('-f', '--force', action='store_true', help='create package even if it already exists')
    group.add_argument('-p', '--platform', help='create package for the given Gitea platform. Valid platforms: %s' % _get_platforms())

    return parser.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    if args.binaries:
        for binary in args.binaries:
            if not os.path.isfile(binary):
                _fail('Binary not found: "%s"' % binary)
            platform = _get_platform(binary=binary)
            arch = _get_arch(platform)
            version = _get_version(binary)
            changelog = _get_changelog(version)
            _create_package(version, arch, platform, changelog, args.force, _target_directory(args.directory))
    elif args.platform:
        arch = _get_arch(args.platform)
        version, changelog = _get_latest_version()
        _create_package(version, arch, args.platform, changelog, args.force, _target_directory(args.directory))
    else:
        arch = _get_package_arch() if not args.arch else args.arch
        platform = _get_platform(arch)
        version, changelog = _get_latest_version()
        _create_package(version, _get_arch(platform), platform, changelog, args.force, _target_directory(args.directory))

