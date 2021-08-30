import os
import sys
import argparse
from pathlib import Path

from .watcher import Watcher

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsView, QApplication, QGraphicsScene, QStatusBar, QGridLayout
from GraphicsView import GraphicsView

from PyQt5.QtOpenGL import QGL, QGLWidget, QGLFormat

from .mmap import MMap, MyLineEdit, StatusBar


# Each map can be linked to a scene
class MindMap(QGraphicsScene):
    def __init__(self, root_dir=None, store_dir=None, filename=None):
        super(MindMap, self).__init__()
        self.root_dir = root_dir
        self.store_dir = store_dir
        self.filename = filename
        # Create a new watcher instance which should actually be for each Sheet
        self.watcher = Watcher(self.root_dir, self.store_dir)
        self.create_new_map()
        self.monitor()
        self.hashes = {}

    def monitor(self):
        pdfs, added = self.watcher.check()
        if added:
            self.files_hashes = self.watcher.proc_data[0]  # file -> (hash, metadata)
            self.hashes_files = self.watcher.proc_data[1]  # hash -> (file, metadata)
        new_hashes = set(self.hashes_files.keys())

    def exit_app(self):
        # check if saving
        # if not:
        pass

    def create_new_map(self):
        if self.root_dir:
            self.create_tree()
            self.mmap = MMap(self, dirtree=self.thought_tree)
        elif self.filename:
            self.mmap = MMap(self, filename=self.filename)
        else:
            self.mmap = MMap(self)

    def create_tree(self):
        self.files = []
        self.thought_tree = {}
        for root, dirs, files_ in os.walk(self.root_dir, topdown=True):
            self.files.append((root, [f for f in files_ if '.pdf' in f]))
        self.gen_tree()

    def gen_tree(self):
        # gen_tree I think is independent of everything else
        index = 0
        root_index = index
        root_thought = self.files[root_index]
        self.thought_tree[0] = {'index': index, 'name': root_thought[0],
                                'parent': None, 'children': [], 'files': root_thought[1]}

        while root_index < len(self.files):
            root_thought = (self.thought_tree[root_index]['name'], self.thought_tree[root_index]['files'])
            for f in self.files:
                if os.path.dirname(f[0]) == root_thought[0]:
                    index += 1
                    self.thought_tree[index] = {'index': index, 'name': f[0],
                                                'parent': root_index, 'children': [], 'files': f[1]}
                    self.thought_tree[root_index]['children'].append(index)
            root_index += 1


# The root dir and everything should be integrated here
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Mindmap for documents')
    parser.add_argument('--root-dir', '-r', type=str, default='',
                        help='The root directory from where to monitor pdf files')
    parser.add_argument('--store-dir', '-s', type=str, default='',
                        help='Store the application data in this directory. Defaults to $HOME/.mindmap')
    parser.add_argument('--file', '-f', type=str, default='',
                        help='Open this file for initial editing')
    args = parser.parse_args()

    root_dir = None
    filename = None
    store_dir = None
    if os.path.exists(args.root_dir):
        print("Trying to populate the thought tree from root dir")
        root_dir = Path(args.root_dir)
    elif os.path.exists(args.file):
        print("Opening file: " + args.file)
        if os.path.exists(args.file):
            filename = Path(args.file)
    else:
        print("No root directory or file given. Creating empty sheet.")

    if not args.store_dir:
        store_dir = Path.joinpath(Path.home(), Path(".mindmap"), Path(args.root_dir.replace('/', '_')))
    else:
        store_dir = Path(args.store_dir)
    if not os.path.exists(store_dir):
        Path.mkdir(store_dir)

    app = QApplication(sys.argv)
    mm = MindMap(root_dir=root_dir, store_dir=store_dir, filename=filename)
    grview = GraphicsView(mm, mm.mmap)
    grview.setCacheMode(grview.CacheBackground)
    grview.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
    grview.setViewport(QGLWidget(QGLFormat(QGL.SampleBuffers)))
    grview.resize(1200, 800)
    line_edit = MyLineEdit(grview)
    status_bar = QStatusBar(grview)
    mm.mmap.init_widgets(line_edit, status_bar)
    # grview.horizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    # grview.verticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    # mm.setSceneRect(0, 0, 1200, 800)
    mm.stickyFocus = True
    grview.fitInView(mm.sceneRect(), Qt.KeepAspectRatio)
    grview.show()
    sys.exit(app.exec_())
