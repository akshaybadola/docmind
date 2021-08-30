import os
import glob
import pickle
import hashlib
from shutil import copyfile
from functools import reduce
from collections import defaultdict


class Watcher(object):
    # proc_data contains items returned by build_hashes
    # 1. A dict indexed by filenames, containing inode_number, mtime, ctime
    # 2. Another dict indexed by inode_number containing filenames, mtime, ctime
    # 3. hashlib and stuff is there only for checking if there are duplicates

    def __init__(self, watch_dir, store_dir):
        self.watch_dir = str(watch_dir)
        self.store_dir = str(store_dir)
        self.filenames = ['index_names', 'index_inodes']
        self.proc_data = [None, None]
        self.first_run = True

    # returns, inode_no, ctime, mtime in that order
    def __fstat(self, x):
        return x[1], (x[-1], x[-2])

    def __build_indices(self, path):
        pdfs = glob.glob(str(path) + '/**/*.pdf', recursive=True)
        filestats = list(zip(*[self.__fstat(os.stat(pdf)) for pdf in pdfs]))
        inodes = filestats[0]
        times = filestats[1]    # ctime, mtimes

        dd_files = defaultdict(list)
        dd_nodes = defaultdict(list)

        dd_files.update(zip(pdfs, [(i, j[0], j[1]) for i, j in zip(inodes, times)]))
        dd_nodes.update(zip(inodes, [(i, j[0], j[1]) for i, j in zip(pdfs, times)]))

        return dd_files, dd_nodes


    def __update_indices(self, index_files, index_inodes, path):
        pdfs = glob.glob(str(path) + '/**/*.pdf', recursive=True)
        filestats = [self.__fstat(os.stat(pdf)) for pdf in pdfs]
        inodes = filestats[0]
        times = filestats[1]    # ctime, mtimes

        dd_files = defaultdict(list)
        dd_nodes = defaultdict(list)
        dd_files.update(zip(pdfs, [(i, j[0], j[1]) for i, j in zip(inodes, times)]))
        dd_nodes.update(zip(inodes, [(i, j[0], j[1]) for i, j in zip(pdfs, times)]))

        # Careful here. Lots of repetitve names
        # new_files is a set difference of current files
        # and old files
        # There can be various cases here.
        # 1. File identifier (any part of uri) has changed but content has not (ctime)
        # 2. File content has changed (due to addition of metadata or other such) (mtime)
        # 3. Both content and uri have changed. (that's just a new file)
        # nin_ofn = new inode old filename
        new_filenames = set(pdfs) - set(index_files.keys())
        new_inodes = set(inodes) - set(index_inodes.keys())
        nin_ofn = set([f for f in new_inodes if dd_nodes[f][0] not in new_filenames])
        deleted_inodes = set(index_inodes.keys()) - set(inodes)
        # ultimately, the file in this context is nothing but a bibliographic record
        # new_inodes and new_filenames may intersect, redundant loop for
        # absolutely new files.
        for fn in new_filenames:
            if dd_files[fn][0] in index_inodes:  # if old inode
                if dd_files[fn][1] > index_inodes[dd_files[fn][0]][1]:  # ctime changed
                    pass        # File renamed
                if dd_files[fn][2] > index_inodes[dd_files[fn][0]][2]:  # mtime changed
                    pass        # File content modified
            else:               # new inode
                # is it a copy of some old file? check hash
                # is it just the old deleted inode? check hash and filename
                pass

        for node in nin_ofn:
            # Is it copy of some old file? check hash
            # Since the entire URI is the same as earlier, perhaps it got recreated
            # What to do with deleted files?
            pass


    def __md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    # Currently not used
    # def __check_files(self):
    #     saves = [os.path.exists(os.path.join(self.store_dir,  f + '.pkl')) for f in self.filenames]
    #     saves_bak = [os.path.exists(os.path.join(self.store_dir,  f + '.pkl.bak')) for f in self.filenames]
    #     saves_status = dict(zip([f + '.pkl' for f in for self.filenames],
    #                             [None for f in for self.filenames]))
    #     saves_status.update(zip([f + '.pkl.bak' for f in for self.filenames],
    #                             [None for f in for self.filenames]))
    #     existing_files = [a or b for a, b in zip([saves, saves_bak])]

    def __read_files(self, bak=False):
        if bak:
            suff = '.pkl.bak'
        else:
            suff = '.pkl'

        for i, fname in enumerate(self.filenames):
            with open(os.path.join(self.store_dir, fname + suff), 'rb') as f:
                self.proc_data[i] = pickle.load(f)

    def __write_files(self, bak=False):
        if bak:
            suff = '.pkl.bak'
        else:
            # backup files first
            for i, fname in enumerate(self.filenames):
                p = os.path.join(self.store_dir, fname)
                copyfile(p + '.pkl', p + '.pkl.bak')
            suff = '.pkl'

        for i, fname in enumerate(self.filenames):
            with open(os.path.join(self.store_dir, fname + suff), 'wb') as f:
                pickle.dump(self.proc_data[i], f)


    def __load_files(self):
        self.first_run = False
        saves = [os.path.exists(os.path.join(self.store_dir, f + '.pkl')) for f in self.filenames]
        # saves_bak = [os.path.exists(os.path.join(self.store_dir, f + '.pkl.bak')) for f in self.filenames]

        if False in saves:
            # basically apply AND for each element in list
            bak_exist = reduce(
                lambda x, y: x and y,
                [os.path.exists(os.path.join(
                    self.store_dir, f + '.pkl.bak')) for f in self.filenames])
            if bak_exist:
                # restore operation
                print("DB Corrupt but found backup files")
                for fname in self.filenames:
                    p = os.path.join(self.store_dir, fname)
                    copyfile(p + '.pkl.bak', p + '.pkl')
                self.__read_files()
                return True
            else:
                # delete old backups as some are missing
                for fname in self.filenames:
                    p = os.path.join(self.store_dir, fname)
                    if os.path.exists(p + '.pkl.bak'):
                        os.remove(p + '.pkl.bak')
                # Simply rebuild index for now
                print("Some files are missing!\n")
                print("And the backups are also not there! First run?")
                print("Building initial index")
                self.proc_data = self.__build_indices(self.watch_dir)
                # __write_files automatically backs up the files, but on a first run
                # there would be no files to backup, so write the bare code here
                for i, fname in enumerate(self.filenames):
                    with open(os.path.join(self.store_dir, fname + '.pkl'), 'wb') as f:
                        pickle.dump(self.proc_data[i], f)
                return False
        else:
            print("Previous saves exist!")
            self.__read_files()
            return True

    # Get initial data and then watch for changes
    # Readability is hampered by self.first_run as its usage
    # is not intuitive
    def check(self, old_pdfs=None):
        added = False
        new_pdfs = set(glob.glob(self.watch_dir + '/**/*.pdf', recursive=True))
        # Only if it's first_run
        if self.first_run:
            added = True
            # If could not load files from either regular pkl or pkl.bak
            if not self.__load_files():
                self.__write_files()
            return new_pdfs, added
        else:
            added = False

        if not old_pdfs:
            old_pdfs = set(self.proc_data[0].keys())
            old_hashes = set(self.proc_data[1].keys())

        # NOTE: What if hash changes but file does not? Check modified stamp
        #       Only while writing something the pickles are backed up Even if
        #       files are moved within the same directory tree this should be
        #       updated as the paths are changed even though the basenames
        #       aren't changed. Though must actually make it work.
        if not self.first_run:
            # new files added
            if new_pdfs - old_pdfs:
                print("Files Changed! Building next iteration of indices")
                self.proc_data = self.__update_hashes(*self.proc_data, self.watch_dir)
                self.__write_files()
                added = True
            # some files deleted
            elif not (new_pdfs - old_pdfs) and len(new_pdfs) < len(old_pdfs):
                print("No new files added but files deleted! Updating index")
                # No need to update hashes but __update_hashes takes care of that
                self.proc_data = self.__update_hashes(*self.proc_data, self.watch_dir)
                self.__write_files()
            # files' directories changed, what if
            else:
                print("No change happened! LOL, nothing to do.")

        return new_pdfs, added
