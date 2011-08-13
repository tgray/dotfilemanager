#!/usr/bin/env python
"""dotfilemanager.py - a dotfiles manager script. See --help for usage
and command-line arguments.

"""
import os,sys,platform

skipDirs = ['CVS',
        'RCS',
        '.git',
        '.gitignore',
        '.cvsignore',
        '.svn',
        '.bzr',
        '.bzrignore',
        '.bzrtags',
        '.hg',
        '.hgignore',
        '.hgrags']

dotfiles_scripts = ['dotfiles', 'dotfilemanager', 'dotfilemanager.py']

# TODO: allow setting hostname as a command-line argument also?
try:
    HOSTNAME = os.environ['DOTFILEMANAGER_HOSTNAME']
except KeyError:
    HOSTNAME = platform.node()
HOSTNAME_SEPARATOR = '__'
    
def tidy(d,report=False):
    """Find and delete any broken symlinks in directory d.
    
    Arguments:
    d -- The directory to consider (absolute path)
    
    Keyword arguments:
    report -- If report is True just report on what broken symlinks are
              found, don't attempt to delete them (default: False)
    
    """
    for f in os.listdir(d):
        path = os.path.join(d,f)
        if os.path.islink(path):
            target_path = os.readlink(path)
            target_path = os.path.abspath(os.path.expanduser(target_path))
            if not os.path.exists(target_path):                
                # This is a broken symlink.
                if report:
                    print 'tidy would delete broken symlink: %s->%s' % (path,target_path)                    
                else:
                    print 'Deleting broken symlink: %s->%s' % (path,target_path)
                    os.remove(path)                    

def get_target_paths(to_dir,report=False):
    """Return the list of absolute paths to link to for a given to_dir.
    
    This handles skipping various types of filename in to_dir and
    resolving host-specific filenames.
    
    """
    paths = []
    filenames = os.listdir(to_dir)
    for filename in filenames:
        path = os.path.join(to_dir,filename)
        if filename.endswith('~'):
            if report:
                print 'Skipping %s' % filename
            continue            
        elif (not os.path.isfile(path)) and (not os.path.isdir(path)):
            if report:
                print 'Skipping %s (not a file or directory)' % filename
            continue
        elif filename.startswith('.'):
            if report:
                print 'Skipping %s (filename has a leading dot)' % filename
            continue
        else:
            if HOSTNAME_SEPARATOR in filename:
                # This appears to be a filename with a trailing
                # hostname, e.g. _muttrc__dulip. If the trailing
                # hostname matches the hostname of this host then we
                # link to it.
                hostname = filename.split(HOSTNAME_SEPARATOR)[-1]
                if hostname == HOSTNAME:
                    paths.append(path)
                else:
                    if report:
                        print 'Skipping %s (different hostname)' % filename
                    continue                    
            else:
                # This appears to be a filename without a trailing
                # hostname.
                if filename + HOSTNAME_SEPARATOR + HOSTNAME in filenames: 
                    if report:
                        print 'Skipping %s (there is a host-specific version of this file for this host)' % filename
                    continue
                else:                                            
                    paths.append(path)    
    return paths

def check_file(root, fn, report):
    fullfn = os.path.join(root, fn)
    if fn.startswith('.'):
        return False
    elif fn in skipDirs:
        if report:
            print 'skipping %s (in skip list)' % fn
        return False
    elif (not os.path.isfile(fullfn)) and (not os.path.isdir(fullfn)):
        if report:
            print 'skipping %s (not a file/directory)' % fn
        return False
    elif fn.endswith('~'):
        if report:
            print 'skipping %s' % fn
        return False
    else:
        return True

def get_dotfiles(to_dir, report = False):
    """Return the list of absolute paths to link to for a given to_dir."""
    paths = {}
    for root, dirs, files in os.walk(to_dir):
        dirs[:] = [d for d in dirs if d not in skipDirs]
        files[:] = [f for f in files if check_file(root, f, report)]
        paths[root] = {'root': root, 'dirs': dirs, 'files': files}
    
    topdir = paths.pop(to_dir)
    to_dot_files = [os.path.join(topdir['root'], f) for f in topdir['files']]
    to_dot_dirs = [os.path.join(topdir['root'], d) for d in topdir['dirs']]
    to_dirs, to_files = [], []
    keys = sorted(paths.keys())
    for path in keys:
        dat = paths[path]
        root, dirs, files = dat['root'], dat['dirs'], dat['files']
        for d in dirs:
            to_dirs.append(os.path.join(root, d))
        for f in files:
            to_files.append(os.path.join(root, f))
    outpaths = {'dot_dirs': to_dot_dirs,
            'dot_files': to_dot_files,
            'sub_dirs': to_dirs,
            'sub_files': to_files}
    return outpaths

def link(from_dir, to_dir, report = False):
    """Make symlinks in from_dir to each file and directory in to_dir.

    Arguments:
    from_dir -- The directory in which symlinks will be created (string,
                absolute path)
    to_dir   -- The directory containing the files and directories that
                will be linked to (string, absolute path)
    
    Keyword arguments:
    report   -- If report is True then only report on the status of
                symlinks in from_dir, don't actually create any new
                symlinks (default: False)
    """
    to_paths = get_dotfiles(to_dir, report)
    dirs = to_paths['dot_dirs']
    dirs.extend(to_paths['sub_dirs'])
    files = to_paths['dot_files']
    files.extend(to_paths['sub_files'])
    outdirs = []
    symlinks = {}
    for p in dirs:
        p_stub = os.path.relpath(p, to_dir)
        p2 = '.' + p_stub
        outp = os.path.join(from_dir, p2)
        outdirs.append(outp)
    for f in files:
        infn = process_file(f, to_paths, report)
        if infn:
            # remove hostname specifiers
            parts = infn.split(HOSTNAME_SEPARATOR)
            assert len(parts) == 1 or len(parts) == 2
            out = parts[0]
            f_stub = os.path.relpath(out, to_dir)
            f2 = '.' + f_stub
            outf = os.path.join(from_dir, f2)
            symlinks[infn] = outf
   
    for d in outdirs:
        d = os.path.abspath(os.path.expanduser(d))
        if os.path.isdir(d):
            if report:
                print "directory %s already exists" % d
            continue
        else:
            if report:
                print "would make: %s" % d
            else:
                print "making %s" % d
                os.makedirs(d)

    for source, target in symlinks.items():
        # Check that nothing already exists at target.
        if os.path.islink(target):
            # A link already exists.
            existing_source = os.readlink(target)
            existing_source = os.path.abspath(
                    os.path.expanduser(existing_source))
            if  existing_source == source:
                # It's already a link to the intended target. All is
                # well.
                # if report:
                    # print 'already linked: %s' % source
                continue
            else:
                # It's a link to somewhere else.
                print target + " => is already symlinked to " + existing_source
        elif os.path.isfile(target):
            print "There's a file in the way at " + target
        elif os.path.isdir(target):
            print "There's a directory in the way at " + target
        elif os.path.ismount(target):
            print "There's a mount point in the way at " + target
        else:
            # The path is clear, make the symlink.
            if report:
                print 'would link: %s -> %s' % (target, source)
            else:
                print 'Making symlink %s -> %s' % (target, source)
                os.symlink(source, target)

def process_file(f, to_paths, report = False):
    tmp, filename = os.path.split(f)
    if filename.endswith('~'):
        if report:
            print 'Skipping %s' % filename
    elif (not os.path.isfile(f)) and (not os.path.isdir(f)):
        if report:
            print 'Skipping %s (not a file or directory)' % filename
    elif filename.startswith('.'):
        if report:
            print 'Skipping %s (filename has a leading dot)' % filename
    elif filename in dotfiles_scripts:
        if report:
            print 'Skipping %s (dotfile script)' % filename
    else:
        if HOSTNAME_SEPARATOR in filename:
            # This appears to be a filename with a trailing
            # hostname, e.g. _muttrc__dulip. If the trailing
            # hostname matches the hostname of this host then we
            # link to it.
            hostname = filename.split(HOSTNAME_SEPARATOR)[-1]
            if hostname == HOSTNAME:
                return f
            else:
                if report:
                    print 'Skipping %s (different hostname)' % filename
        else:
            # This appears to be a filename without a trailing
            # hostname.
            if f + HOSTNAME_SEPARATOR + HOSTNAME in to_paths['dot_files']: 
                if report:
                    print 'Skipping %s (there is a host-specific version of this file for this host)' % filename
            else:
                return f
    return None

def usage():
    return """Usage:

dotfilemanager link|tidy|report [FROM_DIR [TO_DIR]]
    
Commands:
   link -- make symlinks in FROM_DIR to files and directories in TO_DIR
   tidy -- remove broken symlinks from FROM_DIR (but not subdirectories)
   report -- report on symlinks in FROM_DIR and files and directories in TO_DIR
   
FROM_DIR defaults to ~ and TO_DIR defaults to ~/.dotfiles.
   """

if __name__ == "__main__":
    try:
        ACTION = sys.argv[1]
    except IndexError:
        print usage()
        sys.exit(2)

    try:
        FROM_DIR = sys.argv[2]
    except IndexError:
        FROM_DIR = '~'
    FROM_DIR = os.path.abspath(os.path.expanduser(FROM_DIR))

    if not os.path.isdir(FROM_DIR):
        print "FROM_DIR %s is not a directory!" % FROM_DIR
        print usage()
        sys.exit(2)

    if ACTION == 'tidy':
        tidy(FROM_DIR)
    else:

        try:
            TO_DIR = sys.argv[3]
        except IndexError:
            TO_DIR = os.path.join('~','.dotfiles')
        TO_DIR = os.path.abspath(os.path.expanduser(TO_DIR))

        if not os.path.isdir(TO_DIR):
            print "TO_DIR %s is not a directory!" % TO_DIR
            print usage()
            sys.exit(2)

        if ACTION == 'link':
            link(FROM_DIR,TO_DIR)
        elif ACTION == 'report':
            link(FROM_DIR,TO_DIR,report=True)
            tidy(FROM_DIR,report=True)
        else:
            print usage()
            sys.exit(2)
