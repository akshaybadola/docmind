import os
import operator
from functools import reduce, singledispatch

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QBrush, QPainterPath, QPainter, QColor, QPen, QPixmap, QRadialGradient
from PyQt5.QtWidgets import (QGraphicsEllipseItem, QApplication, QGraphicsView, QGraphicsRectItem,QLineEdit,
                             QGraphicsScene, QGraphicsItem, QGraphicsTextItem, QGraphicsPixmapItem,
                             QStatusBar, QGraphicsDropShadowEffect)
from PyQt5.QtOpenGL import QGL, QGLWidget, QGLFormat

from .thought import Thought
from .link import Arrow, Link
from .shape import Shape, Shapes
from .io import load_file, save_file

# Priorities:
# BUG: if I delete some children while in cycle_ and then try to move in opposite movement direction
#              FIXED with adjusting self.cycle_items
# BUG: After partial expand, navigation to child nodes to children and again trying to do partial expand
#              in orthogonal direction causes a crash
#              FIXED with the adjustment to hide_thoughts where if expand_leaves is false, then the node's
#              directional expand flag is set to false if all children are leaves
# 1. Maybe change the expand and collapse behaviours
#     - Space collapses expands all nodes except k-th level (leaves or perhaps one level up from leaves)
#     - Shift_Space collapses and expands all nodes
#     - Control_direction collapses and expands only one level
# 4. Fix expansion, collapse
#     - Hidden and expand flags are not correctly working w.r.t. navigation (though mostly working)
#     - Mouse expand will only work if there's an indicator that there's something to expand
#     - Expansion more robust with checks such that if all directions are 'd', then
#       expand is 'd'
#     -  Add Expansion, contraction by mouse.
# 2. Navigation and expansion although they work fine, sometimes the keystrokes don't
#     do what is expected of them (require more than one keypress or navigate to disconnected nodes)


# Most of it seems to be working fine now. Maybe a few bugs are still there, we can deal with them later.
#
# 0. File Hashes and directory watching
# 1. All prompts and information in the status bar
# 1. Placement while populating tree is still a bit messy and there's no adjust_thoughts
#     implmentation.
# 5. Partial expand automatically if the hidden node contains a search term
#     - Expand alongside siblings? Or just the node?
# 2. Left, Right, Up, Down are also bound to scrolling the GraphicsView
#     - Must change those to something else.
# 3. Alignment while re-placing children is incorrect if added anywhere, either modify place_child
#     or write a new function for it.
#     - Alignment is also incorrect for new children if the width of the window is too long
#       Must adjust.
# 4. If a node has too many files, then perhaps show only a few but scroll through all
#     maybe ability to search through them also selectively


# 1. Add a "star" to a file, perhaps of different colors (importance or groupings)
#     and should be able to highlight the relevant starred files, while either
#     hiding others or making them transluscent but still available
# 4. Basic emacs like key-bindings for the text editor
# 3. Do I need node resize?
# b) Add a child to each pdf node which by default is always collapsed but
#     expands on demand(with animation) as the node is selected and shows
#     the description (which may or may not be there) for that file
# 1. Customizable key-mappings, with a template to automatically
#     do it from a config file


# 10. Change all dicts to enums?
# 1. Links between nodes other than with a parent child relationship
#     And a way to show/hide them and navigate between them
# 2. *Color hierarchy. I'm not ready to put color choosers yet there
#      - Colors other than red are there now, but they're still bound to shape
# 3. Children should snap close to each other
# 4. An overall method to adjust everything according to some rules
# 6. Also a way to move children from one side to another (with animation)
# 9. Panning, zoom (wtf is that and how to handle wrt saves and restore)
# 10. Animation while expansion and contraction
# 14. *Should insert new nodes away from other nodes as well and not
#       just nodes in family (minimize overlap while insertion)
#       - In fact it can be that the childrens' position is fixed just like
#         the thoughts' size is fixed corresponding to the text that they have
#       - I'm thinking of an animation while reordering siblings, like in tabs
# 17. Splines
# 19. Perhaps expand with just the movement? and expand and collapse on demand?
# 20. Better looking nodes. Currently they look like shit
#       - They actually look fairly ok now. I have to add animations however.
# 21. Append a node to the current level of hierarchy
#      - I think that can be accomplished fairly easily as the node would have to be
#        some other node's child
# 23. There should be an option to show the directory tree k-level deep, i.e., show
#       till kth-level expanded and the rest collapsed.
# 24. Cycle items should only cycle between visible items and not hidden ones (Is this needed now?)
# 25. Tabular format for all the pdfs (or selected pdfs or families) for mendeley like environment
#       in QtQuick
# 26. Pdf previews in tiny windows which are children of the top level window or ideally, the scene


class StatusBar(QStatusBar):
    # Maybe a custom implementation of the statutsbar
    # for keybindings and stuff
    pass


class MyLineEdit(QLineEdit):
    def __init__(self, *args):
        super(MyLineEdit, self).__init__(*args)
        self.text_dict = {}
        self.twt = None

    def set_mmap(self, mmap):
        self.mmap = mmap

    def update_text(self):
        for k, v in self.mmap.thoughts.items():
            if not self.mmap.thoughts[k].hidden:
                self.text_dict[k] = v.text.lower()
            else:
                self.text_dict[k] = ''

    def highlight(self):
        text = self.text()
        twt = []
        for k, v in self.text_dict.items():
            if text in v:
                twt.append(k)
        self.twt = twt
        self.mmap.highlight(twt)

    def keyPressEvent(self, event):
        if event.key() in {Qt.Key_Escape, Qt.Key_Return} or\
           (event.key() in {Qt.Key_G, Qt.Key_S} and event.modifiers() & Qt.ControlModifier):
            self.mmap.search_toggle()
            event.accept()
        elif event.key() in {Qt.Key_P, Qt.Key_N} and event.modifiers() & Qt.ControlModifier:
            if self.mmap.cycle_items:
                self.mmap.search_cycle(event.key())
            else:
                self.mmap.toggle_search_cycle(self.twt)
        else:
            super().keyPressEvent(event)
            self.mmap.toggle_search_cycle(toggle=False)
            self.highlight()
            event.accept()


class MMap(object):
    def __init__(self, scene, filename=None, dirtree=None):
        self.scene = scene
        self.root_dir = None
        self.filename = filename
        self.dirtree = dirtree
        self.default_insert = 'u'
        self.typing = False

        self.dir_map = {'pos': {'horizontal': 'r', 'vertical': 'd'},
                        'neg': {'horizontal': 'l', 'vertical': 'u'},
                        'l': ('neg', 'horizontal'),
                        'r': ('pos', 'horizontal'),
                        'u': ('neg', 'vertical'),
                        'd': ('pos', 'vertical'),
                        'horizontal': ('l', 'r'),
                        'vertical': ('u', 'd')}
        self.inverse_map = {'l': 'r', 'r': 'l', 'u': 'd', 'd': 'u',
                            'horizontal': ('u', 'd'), 'vertical': ('l', 'r')}
        self.inverse_orientmap = {'horizontal': 'vertical', 'vertical': 'horizontal',
                                  'l': 'vertical', 'r': 'vertical', 'u': 'horizontal', 'd': 'horizontal'}
        self.orient_map = {'l': 'horizontal', 'u': 'vertical', 'r': 'horizontal', 'd': 'vertical'}
        self.other_dirmap = {'l': {'u', 'd', 'r'},
                             'r': {'u', 'd', 'l'},
                             'u': {'l', 'd', 'r'},
                             'd': {'u', 'l', 'r'}}
        self.op_map = {'l': (-200, 0), 'r': (200, 0), 'u': (0, -200), 'd': (0, 200)}
        self.movement = None
        self.cycle_index = 0
        self.cycle_items = []
        self.toggled_search = False
        self.get_selected = self.scene.selectedItems
        self.transluscent = set()
        self.thoughts = {}
        self.links = {}
        self.selections = []
        self.cur_index = 0
        self.arrows = []
        self.pix_items = []
        self.thought_positions = []
        self.dragging_items = []
        self.target_item = None

        self.coo_x = singledispatch(self.coo_x)
        self.coo_x.register(int, self._coo_x_int)
        self.coo_x.register(Shape, self._coo_x_shape)
        self.coo_x.register(Thought, self._coo_x_thought)
        self.coo_y = singledispatch(self.coo_y)
        self.coo_y.register(int, self._coo_y_int)
        self.coo_y.register(Shape, self._coo_y_shape)
        self.coo_y.register(Thought, self._coo_y_thought)
        self.coo = singledispatch(self.coo)
        self.coo.register(Thought, self._coo_thought)
        self.coo.register(Shape, self._coo_shape)

        if self.dirtree:
            # tt_map == tree_thought_map
            self.tt_map = {}
            self.root_dir = self.dirtree[0]['name']
            self.populate_tree()
        elif self.filename:
            self.load_data()
            # except Exception:
            #     print("Some weird error occured while trying to populate canvas.\nThe program will exit")
            #     sys.exit()

    def init_widgets(self, search_widget, status_bar):
        self.search_widget = search_widget
        self.search_widget.set_mmap(self)
        self.search_widget.setVisible(False)
        self.status_bar = status_bar
        self.status_bar.setSizeGripEnabled(False)
        self.status_bar.setStyleSheet("background-color: white")
        self.status_bar.setVisible(True)
        self.status_bar.show()
        self.status_bar.showMessage("Ready...", 0)

    def reposition_status_bar(self, geom):
        rect = geom.getRect()
        self.status_bar.setGeometry(0, rect[3] - 40, rect[2], 50)

    def save_data(self, filename=None):
        print("trying to save data")
        self.status_bar.showMessage("trying to save data", 0)
        if not filename:
            filename = '/home/joe/test.json'
        data = {}
        data['root_dir'] = self.root_dir
        data['thoughts'] = []
        for t in self.thoughts.values():
            data['thoughts'].append(t.serialize())
        data['links'] = list(zip(list(self.links.keys()), [l.direction for l in self.links.values()]))
        save_file(data, filename)
        self.status_bar.showMessage("Saved to file" + filename, 0)

    def load_data(self, filename=None):
        print ("trying to load data")
        if not filename:
            filename = '/home/joe/test.json'
        data = load_file(filename)
        if data == {}:
            return
        if 'root_dir' in data:
            self.root_dir = data['root_dir']
        for t in data['thoughts']:
            self.add_thought(QPointF(t['coords'][0], t['coords'][1]), data=t)  # will this work? I don't think so
        links_data = data['links']
        for l in links_data:
            self.add_link(l[0][0], l[0][1], l[1])
        for t in self.thoughts.keys():
            for lk in self.links.keys():
                if t in lk and self.thoughts[t].hidden:
                    self.links[lk].setVisible(False)

    def add_thought(self, pos, shape=None, text="test thought", pdf=None, data={}):
        if pdf:
            text = os.path.basename(pdf).replace('.pdf', '')
        elif 'pdf' in data:
            text = os.path.basename(data['pdf']).replace('.pdf', '')
        if not shape:
            shape = Shapes['rounded_rectangle']
        self.cur_index += 1
        self.thoughts[self.cur_index] = Thought(self, self.cur_index, shape, pos, text=text, pdf=pdf, data=data)
        self.scene.update()

    # What about children and parents' and siblings' dicts?
    # Perhaps attach to next up in hierarchy?
    def delete_thought(self, thought):
        ind = thought.index
        if self.cycle_items:
            self.cycle_items.remove(ind)
        for i in thought.family['children']:
            self.thoughts[i].family['parent'] = None
            for c in ['u', 'd', 'l', 'r']:
                if 'siblings' in self.thoughts[i].family[c]:
                    self.thoughts[i].family[c].pop('siblings')
                if 'parent' in self.thoughts[i].family[c]:
                    self.thoughts[i].family[c].pop('parent')
        par = thought.family['parent']
        if par:
            par = self.thoughts[par]
            children = par.family['children']
            children.remove(ind)
            for c in ['u', 'd', 'l', 'r']:
                if 'children' in par.family[c]:
                    if ind in par.family[c]['children']:
                        par.family[c]['children'].remove(ind)
            for child in children:
                child = self.thoughts[child]
                for c in ['u', 'd', 'l', 'r']:
                    if 'siblings' in child.family[c]:
                        if ind in child.family[c]['siblings']:
                            child.family[c]['siblings'].remove(ind)
                self.fix_family(child)
            self.fix_family(par)
        thought.remove()
        self.thoughts.pop(ind)
        links_to_remove = [l for l in self.links.keys() if ind in l]
        for l in links_to_remove:
            self.scene.removeItem(self.links[l])
            self.links.pop(l)

    def add_link(self, t1_ind, t2_ind, direction=None):
        if not direction:
            print("cannot insert link without direction")
        self.links[(t1_ind, t2_ind)] = Link(self.thoughts[t1_ind], self.thoughts[t2_ind], self.thoughts[t1_ind].color, scene=self.scene, direction=direction)
        self.scene.addItem(self.links[(t1_ind, t2_ind)])
        self.scene.update()

    def update_pos(self):
        for thought in self.thoughts.values():
            thought.coords = thought.mapToScene(thought.pos())
            thought.shape_coords = (thought.shape_item.pos().x(), thought.shape_item.pos().y())

    def dist_pos(self, pos1, pos2):
        return (pos1.x() - pos2.x()) ** 2 + (pos1.y() - pos2.y()) ** 2

    def text_uneditable_all(self):
        for ts in self.thoughts.values():
            ts.setTextInteractionFlags(Qt.NoTextInteraction)

    # this should also be easier
    def check_mouse_selection(self, event):
        pass

    # perhaps not needed
    def select(self, ind):
        self.thoughts[ind].shape_item.setSelected(True)

    def select_descendants(self, thoughts):
        recurse_ = []
        for t in thoughts:
            if isinstance(t, Shape):
                t.setSelected(True)
                t = t.text_item
            elif isinstance(t, Thought):
                t.shape_item.setSelected(True)
            if t.family['children']:
                recurse_ += [self.thoughts[i] for i in t.family['children']]
        if recurse_:
            self.select_descendants(recurse_)
        else:
            return

    def select_all(self):
        selected = self.scene.selectedItems()
        if not selected:
            for ts in self.thoughts.values():
                ts.shape_item.setSelected(True)
        else:
            if len(selected) == 1:
                thought = selected[0].text_item
                for c in ['u', 'd', 'l', 'r']:
                    if 'siblings' in thought.family[c]:
                        for s in thought.family[c]['siblings']:
                            self.select(s)

    # links also?
    def unselect_all(self):
        self.scene.clearSelection()

    def select_new_thought(self):
        self.select_one(self.cur_index)
        self.thoughts[self.cur_index].set_editable()

    def coo_x(self, tt):
        return

    def coo_y(self, tt):
        return

    def _coo_x_int(self, t_ind):
        return self.thoughts[t_ind].shape_item.pos().x()

    def _coo_x_shape(self, t):
        return t.pos().x()

    def _coo_x_thought(self, t):
        return t.shape_item.pos().x()

    def _coo_y_int(self, t_ind):
        return self.thoughts[t_ind].shape_item.pos().y()

    def _coo_y_shape(self, t):
        return t.pos().y()

    def _coo_y_thought(self, t):
        return t.shape_item.pos().y()

    def coo(self, tt):
        return

    def _coo_thought(self, t):
        return t.shape_item.pos()

    def _coo_shape(self, t):
        return t.pos()

    # def dist(self, item1, item2):
    #     return (item1.pos().x() - item2.pos().x()) ** 2 + (item1.pos().y() - item2.pos().y()) ** 2

    def dist(self, x, y):
        if isinstance(x, Shape):
            if isinstance(y, Shape):
                return (x.pos().x() - y.pos().x()) ** 2 + (x.pos().y() - y.pos().y()) ** 2
            elif isinstance(y, Thought):
                return (x.pos().x() - y.shape_item.pos().x()) ** 2 + (x.pos().y() - y.shape_item.pos().y()) ** 2
            elif isinstance(y, QPointF):
                return (x.pos().x() - y.x()) ** 2 + (x.pos().y() - y.y()) ** 2
            elif isinstance(y, tuple):
                return (x.pos().x() - y[0]) ** 2 + (x.pos().y() - y[1]) ** 2
        elif isinstance(x, Thought):
            if isinstance(y, Shape):
                return (x.shape_item.pos().x() - y.pos().x()) ** 2 + (x.shape_item.pos().y() - y.pos().y()) ** 2
            elif isinstance(y, Thought):
                return (x.pos().x() - y.pos().x()) ** 2 + (x.pos().y() - y.pos().y()) ** 2
            elif isinstance(y, QPointF):
                return (x.pos().x() - y.x()) ** 2 + (x.pos().y() - y.y()) ** 2
            elif isinstance(y, tuple):
                return (x.pos().x() - y[0]) ** 2 + (x.pos().y() - y[1]) ** 2
        elif isinstance(x, QPointF):
            if isinstance(y, Shape):
                return (x.x() - y.pos().x()) ** 2 + (x.y() - y.pos().y()) ** 2
            elif isinstance(y, Thought):
                return (x.x() - y.pos().x()) ** 2 + (x.y() - y.pos().y()) ** 2
            elif isinstance(y, QPointF):
                return (x.x() - y.x()) ** 2 + (x.y() - y.y()) ** 2
            elif isinstance(y, tuple):
                return (x.x() - y[0]) ** 2 + (x.y() - y[1]) ** 2
        elif isinstance(x, tuple):
            if isinstance(y, Shape):
                return (x[0] - y.pos().x()) ** 2 + (x[1] - y.pos().y()) ** 2
            elif isinstance(y, Thought):
                return (x[0] - y.pos().x()) ** 2 + (x[1] - y.pos().y()) ** 2
            elif isinstance(y, QPointF):
                return (x[0] - y.x()) ** 2 + (x[1] - y.y()) ** 2
            elif isinstance(y, tuple):
                return (x[0] - y[0]) ** 2 + (x[1] - y[1]) ** 2

    # @singledispatch
    # def coo_x(self, t):
    #     return t.pos().x()

    # @coo_x.register(int)
    # def _(self, t_ind):
    #     return self.thoughts[t_ind].shape_item.pos().x()

    # @singledispatch
    # def coo_y(self, t):
    #     return t.pos().y()

    # @coo_y.register(int)
    # def _(self, t_ind):
    #     return self.thoughts[t_ind].shape_item.pos().y()

    # do i really need these? If t's parent is not scene, then yes
    def coo_mx(self, t):
        return t.mapToScene(t.pos()).x()

    def coo_my(self, t):
        return t.mapToScene(t.pos()).y()

    def links_zvalue(self, t, value=1):
        for k in self.links.keys():
            if t.index in k:
                self.links[k].setZValue(value)

    # This function is not called at all
    # I might have to override paint in the Link to get it the shadow to work correctly
    # def update_links(self):
    #     for link in self.links.values():
    #         link.updatePosition()
    #     self.scene.update()

    # I think zoom's taken care of, but have to find a way to
    # measure it and add that to save file
    def zoom(self):
        pass

    def populate_tree(self):
        # build a _file_ thought for each filename. Add hashes later
        # But def_ins in children nodes should not be minority but
        # should be adaptive Indeed there should be different kinds of
        # links for such tasks. The rest of the code can be put in a
        # loop children nodes which are directories.
        #
        # Takes a nodelist
        # as argument to facilitate recursion nodeList is a list of
        # indices

        keys = list(self.dirtree.keys())
        keys.sort()
        self.add_thought(QPointF(1.0, 1.0), Shapes['circle'],
                         data={'text': os.path.basename(self.dirtree[keys[0]]['name']), 'color': 'red', 'side': 'u'})
        self.tt_map[keys[0]] = self.cur_index
        self.populate_children(self.dirtree[keys[0]])

    def populate_children(self, node, insert=None):
        # Add children with other possible children (i.e. files) in the opposite direction to the parent
        # Add files to one side, but make sure that if the sibling next to has files on one side, then
        # for itself the node adds on the other side

        # get side, check on siblings side (left, right) or (up, down)
        # check on one side, if there's sibling, check if sibling's children there
        # left, up are the default directions for now
        pind = self.tt_map[node['index']]
        p = self.thoughts[pind]
        direction = self.inverse_map[self.orient_map[p.side]][0]
        # These will have files, but they'll be added later. Note that their children
        # are not being added

        def pop_files():
            for f in node['files']:
                self.add_new_child(
                    p, data={'text': os.path.basename(f), 'pdf': os.path.join(node['name'], f), 'color': 'yellow'},
                    shape=Shapes['rectangle'], direction=direction)
                p.part_expand[direction] = 'd'
                p.expand = 'e'
                self.thoughts[self.cur_index].check_hide(True)
                self.links[p.index, self.cur_index].setVisible(False)

        def pop_dirs():
            for d in node['children']:
                self.add_new_child(
                    p, data={'text': os.path.basename(self.dirtree[d]['name']), 'color': 'green'},
                    shape=Shapes['ellipse'], direction=p.side)
                self.tt_map[d] = self.cur_index

        def recurse_():
            for d in node['children']:
                self.populate_children(self.dirtree[d])

        pop_dirs()
        pop_files()
        recurse_()


    def highlight(self, t_inds):
        op_inds = t_inds
        all_inds = set(self.thoughts.keys())
        tl_inds = all_inds.difference(set(t_inds))
        for t in tl_inds:
            self.thoughts[t].set_transluscent()
        for t in op_inds:
            self.thoughts[t].set_opaque()
        if t_inds:
            self.select_one(set(op_inds))

    def un_highlight(self):
        for t in self.thoughts.values():
            t.set_opaque()

    def drag_and_drop(self, event, pos=None, pdf=None):
        if not pdf:
            return
        # pos = event.pos()
        selected = self.scene.selectedItems()
        parent = None
        if selected:
            if len(selected) == 1:
                parent = selected[0]
            if isinstance(parent, Shape):
                parent = parent.text_item
            coords = [QPointF(x[0], x[1]) for x in parent.shape_item.get_link_coords()]
            dirs = ['l', 'u', 'r', 'd']
            dirz = dict(zip(dirs, coords))
            possible_directions = [d for d in dirs if parent.family[d][0] not in {'parent', 'siblings'}]
            dist_dir = [(self.dist_pos(pos, parent.mapToScene(dirz[p])), p) for p in possible_directions]
            res = min(dist_dir, key=lambda x: x[0])
            # res = min(
            #     [(self.dist_pos(pos, dirz[p]), p) for p in possible_directions],
            #     key=lambda x: x[0])
            self.add_new_child(parent, direction=res[1], data={'pdf': pdf})
        else:
            self.add_thought(pos, pdf=pdf)

    def place_child(self, parent, direction):
        shape_item = parent.shape_item  # shape item for that thought

        def child_thoughts(parent, c_inds):
            return map(lambda x: self.thoughts[x], parent.family[direction]['children'])

        pos = None
        axis, orientation = self.dir_map[direction]
        displacement = 200
        buffer = 20
        if 'parent' in parent.family[direction]:  # [0] == 'parent':  # or parent.family[direction][0] == 'siblings':
            return
        x = self.coo_x(shape_item)
        y = self.coo_y(shape_item)
        if 'children' in parent.family[direction]:
            children = parent.family[direction]['children']
            on_side = None
            child_axis = None
            if direction in {'l', 'r'}:
                on_side = [1 if self.coo_y(c) < y else 0 for c in child_thoughts(parent, children)]
            elif direction in {'u', 'd'}:
                on_side = [1 if self.coo_x(c) < x else 0 for c in child_thoughts(parent, children)]
            if sum(on_side) < len(on_side)/2:
                child_axis = 'neg'
            else:
                child_axis = 'pos'
            lco = self.last_child_ordinate(children, 'horizontal'
                                           if orientation == 'vertical'
                                           else 'vertical', child_axis)
            if direction == 'l':
                if child_axis == 'neg':
                    pos = QPointF(x - displacement, lco - buffer)
                else:
                    pos = QPointF(x - displacement, lco + buffer)
            elif direction == 'r':
                if child_axis == 'neg':
                    pos = QPointF(x + displacement +
                                  shape_item.boundingRect().getRect()[2], lco - buffer)
                else:
                    pos = QPointF(x + displacement +
                                  shape_item.boundingRect().getRect()[2], lco + buffer)
            elif direction == 'u':
                if child_axis == 'neg':
                    pos = QPointF(lco - buffer, y - displacement)
                else:
                    pos = QPointF(lco + buffer, y - displacement)
            elif direction == 'd':
                if child_axis == 'neg':
                    pos = QPointF(lco - buffer, y + displacement + shape_item.boundingRect().getRect()[3])
                else:
                    pos = QPointF(lco + buffer,
                                  y + displacement + shape_item.boundingRect().getRect()[3])
        else:
            if orientation == 'horizontal':
                if axis == 'neg':  # l
                    pos = QPointF(x - displacement, y)
                else:  # r
                    pos = QPointF(x + displacement + shape_item.boundingRect().getRect()[2], y)
            else:
                if axis == 'neg':  # u
                    pos = QPointF(x, y - displacement)
                else:  # d
                    pos = QPointF(x, y + displacement + shape_item.boundingRect().getRect()[3])
        return pos

    def add_new_child(self, parent, data={}, shape=Shapes['rectangle'], direction=None):
        if isinstance(parent, Shape):
            parent = parent.text_item
        if not direction:
            direction = parent.insert_dir
        axis, orientation = self.dir_map[direction]
        pos = self.place_child(parent, direction)
        data.update({'side': direction})
        self.add_thought(pos, text="child thought", shape=shape, data=data)
        if 'children' in parent.family[direction]:         # update parent direction
            parent.family[direction]['children'].add(self.cur_index)
        else:
            parent.family[direction].update({'children': {self.cur_index}})
        parent.family['children'].add(self.cur_index)        # update parent's children
        c_t = self.thoughts[self.cur_index]
        idir = self.inverse_map[direction]
        # iorient = self.inverse_map[orientation]
        c_t.family['parent'] = parent.index
        c_t.family[idir] = {'parent': parent.index}
        self.update_siblings(parent, c_t, direction)
        self.add_link(parent.index, self.cur_index, direction=direction)
        # self.adjust_thoughts()

    def fix_family(self, thought):
        for c in ['l', 'u', 'r', 'd']:
            keys = list(thought.family[c].keys())
            for k in keys:
                if not thought.family[c][k]:
                    thought.family[c].pop(k)

    def to_pixmap(self, items):
        for item in items:
            p = self.scene.addPixmap(item.to_pixmap())
            p.setPos(item.pos())
            p.setFlag(QGraphicsItem.ItemIsSelectable, False)
            p.setFlag(QGraphicsItem.ItemIsMovable, False)
            self.pix_items.append(p)

    def try_attach_children(self, event, items=None, drag_state='begin'):
        if drag_state == 'begin':
            self.drag_begin_pos = event.pos()
            self.dragging_items = items
            for t in self.dragging_items:
                self.thought_positions.append(self.coo(t))
                self.to_pixmap(self.dragging_items)
        elif drag_state == 'dragging':
            if self.dragging_items:
                for di in self.dragging_items:
                    di.text_item.set_transluscent(0.6)
                totalRect = reduce(operator.or_, (i.sceneBoundingRect() for i in self.dragging_items))
                tr = totalRect.getRect()
                buf = 40
                totalRect = QRectF(tr[0] - buf, tr[1] - buf, tr[2] + 2 * buf, tr[3] + 2 * buf)
                self.scene.addRect(totalRect)
                intersection = self.scene.items(totalRect, Qt.IntersectsItemBoundingRect)
                items = list(filter(lambda x: isinstance(x, Shape) and x not in self.dragging_items, intersection))
                if not items:
                    for arrow in self.arrows:
                        self.scene.removeItem(arrow)
                    self.arrows = []
                    self.target_item = None
                elif items and self.target_item != items[0]:
                    for arrow in self.arrows:
                        self.scene.removeItem(arrow)
                    self.arrows = []
                    self.target_item = None
                    self.target_item = items[0]
                    for di in self.dragging_items:
                        a = Link(di, items[0], QColor(80, 90, 100, 255), collide=True)
                        self.scene.addItem(a)
                        self.arrows.append(a)
                        self.scene.update()
        elif drag_state == 'end':
            if not self.target_item:
                for i, tpos in enumerate(self.thought_positions):
                    self.dragging_items[i].setPos(tpos)
                    self.dragging_items[i].text_item.set_opaque()
                self.dragging_items = []
                for p in self.pix_items:
                    self.scene.removeItem(p)
                self.pix_items = []
                for a in self.arrows:
                    self.scene.removeItem(a)
                self.arrows = []
                self.target_item = None
                self.thought_positions = []
            else:
                for p in self.pix_items:
                    self.scene.removeItem(p)
                self.pix_items = []
                for a in self.arrows:
                    self.scene.removeItem(a)
                self.arrows = []
                self.thought_positions = []
                for item in self.dragging_items:
                    item.text_item.set_opaque()
                self.update_parent(self.dragging_items, self.target_item)
                self.target_item = None
                self.scene.update()

    def attach_dir(self, target, c_inds):
        if isinstance(target, Thought):
            coords = target.shape_item.get_link_coords()
            tlc = [target.shape_item.mapToScene(c[0], c[1]) for c in coords]
        else:
            coords = target.get_link_coords()
            tlc = [target.mapToScene(c[0], c[1]) for c in coords]

        def xx(x):
            return x.mapToScene(x.boundingRect().center()).x()

        def xy(x):
            return x.mapToScene(x.boundingRect().center()).y()

        x_ = sum([xx(self.thoughts[ind]) for ind in c_inds])/len(c_inds)
        y_ = sum([xy(self.thoughts[ind]) for ind in c_inds])/len(c_inds)
        return ['l', 'u', 'r', 'd'][
            min([(j, self.dist((x_, y_), tlc[j])) for j in range(4)], key=lambda x: x[1])[0]]

    # Links remain drawn needlessly
    def update_parent(self, children, target):
        # if there are multiple famillies, find the highest member in each
        # What if I only attach the parent and not the children?
        # Currently it's assumed that the children move with the parent
        indices = set([child.index for child in children])
        indices_full = indices.copy()
        filtered = [c for c in children]
        ol = len(filtered)

        diff = 1
        while (diff):
            for f in filtered:
                if f.family['parent'] in indices:
                    indices.remove(f.index)
            filtered = list(filter(lambda c: c.index in indices, children))
            diff = ol - len(filtered)
            ol = len(filtered)

        # indices has the top level nodes
        # for each index check parent, children and siblings
        # change parent to target, change children to only those which are in selection
        # change siblings to union which are in selection and children of newly attached parent
        # for those which are not top-level, change siblings and children

        # For each top level node that is attached, attach them in the same direction.
        #  - change the directions of all their children to away from the parent node

        # The direction now is correct w.r.t. the average of the top level nodes
        # I'm not dealing with the old family though.
        # Remove old family, attach to new one
        direction = self.attach_dir(target, indices)
        idir = self.inverse_map[direction]
        for ind in indices:
            t = self.thoughts[ind]

            # remove from old family
            t_pind = t.family['parent']
            if t_pind:
                t_par = self.thoughts[t.family['parent']]
                d_0, d_1 = self.inverse_map[self.orient_map[t.side]]
                # First remove sibling
                for sib in t_par.family[t.side]['children']:
                    if 'siblings' in self.thoughts[sib].family[d_0] and t.index in self.thoughts[sib].family[d_0]['siblings']:
                        self.thoughts[sib].family[d_0]['siblings'].remove(t.index)
                    if 'siblings' in self.thoughts[sib].family[d_1] and t.index in self.thoughts[sib].family[d_1]['siblings']:
                        self.thoughts[sib].family[d_1]['siblings'].remove(t.index)

                t_par.family['children'].remove(t.index)
                t_par.family[t.side]['children'].remove(t.index)
                self.fix_family(self.thoughts[sib])
                self.scene.removeItem(self.links[(t_par.index, t.index)])
                self.links.pop((t_par.index, t.index))
            # Add to new family.  At addition the positions of
            # all children of attached nodes should be updated.
            t.family['parent'] = target.index
            t.side = direction
            if 'children' in t.family[idir]:
                self.replace_children(t, idir, direction)

            # clean the thought
            for c in ['u', 'd', 'l', 'r']:
                if 'children' in t.family[c] and (c != direction):
                    self.replace_children(t, c, c)
                if 'siblings' in t.family[c]:
                    t.family[c].pop('siblings')
                if 'parent' in t.family[c]:
                    t.family[c].pop('parent')
            self.fix_family(t)
            target.family['children'].add(t.index)
            if 'children' in target.family[direction]:
                target.family[direction]['children'].add(t.index)
            else:
                target.family[direction]['children'] = {t.index}
            t.family[idir] = {'parent': target.index}
            self.fix_place_children(self.thoughts[ind])
            self.add_link(target.index, t.index, direction)
            self.update_siblings(target, t, direction)

    def update_siblings(self, par, child, direction):
        iorient = self.inverse_map[self.orient_map[direction]]
        # avoid adding self to siblings, although in most other cases self is sibling
        if 'children' in par.family[direction] and len(par.family[direction]['children']) > 1:
            if 'children' not in child.family[iorient[0]]:
                child.family[iorient[0]].update({'siblings': None})
            if 'children' not in child.family[iorient[1]]:
                child.family[iorient[1]].update({'siblings': None})
            for i in par.family[direction]['children']:
                self.thoughts[i].family[iorient[0]]['siblings'] = par.family[direction]['children'].copy()
                self.thoughts[i].family[iorient[1]]['siblings'] = par.family[direction]['children'].copy()

    def fix_place_children(self, parent):
        for c in ['u', 'd', 'l', 'r']:
            if 'children' in parent.family[c]:
                self.replace_children(parent, c, c)
                for child in parent.family[c]['children']:
                    self.fix_place_children(self.thoughts[child])

    # Currently it replaces children from one direction to opposite
    # But I'd like to replace it from any direction to any other feasible direction
    def replace_children(self, par, f_dir, to_dir):  # , children=None):
        if f_dir == to_dir:
            children = par.family[f_dir].pop('children')
            for c_ind in children:
                pos = self.place_child(par, f_dir)
                self.thoughts[c_ind].shape_item.setPos(pos)
                if 'children' in par.family[f_dir]:
                    par.family[f_dir]['children'].add(c_ind)
                else:
                    par.family[f_dir]['children'] = {c_ind}
            return
        else:
            direction = to_dir
            idir = f_dir
            iorient = self.inverse_map[self.orient_map[direction]]
            for c_ind in par.family[idir]['children']:
                self.thoughts[c_ind].family[idir] = {'parent': par.index}
                if 'parent' in self.thoughts[c_ind].family[idir]:
                    self.thoughts[c_ind].family[direction] = {}
                if 'children' in par.family[direction]:
                    par.family[direction]['children'].add(c_ind)
                else:
                    par.family[direction] = {'children': {c_ind}}
                pos = self.place_child(par, direction)
                self.thoughts[c_ind].shape_item.setPos(pos)
                self.thoughts[c_ind].side = direction
                self.scene.removeItem(self.links[(par.index, c_ind)])
                self.add_link(par.index, c_ind, direction)
                self.check_hide_links(c_ind)
                if 'children' not in self.thoughts[c_ind].family[iorient[0]]:
                    self.thoughts[c_ind].family[iorient[0]] = {'siblings': par.family[direction]['children']}
                if 'children' not in self.thoughts[c_ind].family[iorient[1]]:
                    self.thoughts[c_ind].family[iorient[1]] = {'siblings': par.family[direction]['children']}
                if 'children' in self.thoughts[c_ind].family[idir]:
                    self.replace_children(self.thoughts[c_ind], idir, direction)
            par.family[idir].pop('children')
            self.fix_family(par)

    def last_child_ordinate(self, t_inds, orientation, axis):
        if orientation == 'horizontal':
            coo = self.coo_x
        else:
            coo = self.coo_y
        if axis == 'pos':
            func = max
            op = operator.add
        else:
            func = min
            op = operator.sub

        axes = [(t_ind, coo(t_ind)) for t_ind in t_inds]
        retval = func(axes, key=lambda x: x[1])
        return op(retval[1], self.thoughts[retval[0]].shape_item.boundingRect().getRect()[
            2 if orientation == 'horizontal' else 3])

    # def lowest_thought(self, t_inds):
    #     y_axis = [(t_ind, self.coo_y(t_ind))
    #               for t_ind in t_inds]
    #     retval = max(y_axis, key=lambda x: x[1])
    #     return retval[1] + self.thoughts[retval[0]].shape_item.boundingRect().getRect()[3]

    # def rightmost(self, t_inds):
    #     x_axis = [(t_ind, self.coo_x(t_ind))
    #               for t_ind in t_inds]
    #     retval = max(x_axis, key=lambda x: x[1])
    #     return retval[1] + self.thoughts[retval[0]].shape_item.boundingRect().getRect()[2]

    def select_one(self, t_ind):
        if isinstance(t_ind, set):
            t = self.thoughts[list(t_ind)[0]]
        else:
            t = self.thoughts[t_ind]
        if t.shape_item.isVisible():
            self.unselect_all()
            t.shape_item.setSelected(True)
            gview = self.scene.views()[0]
            gview.ensureVisible(t.shape_item)

    def adjust_thoughts(self):
        # get collisions
        # Always between some new child and some other node
        # Which direction is the child added, move away until no collision?
        # Collision from the other side, move that also away. No, that causes trouble (Why?)
        t = self.thoughts[self.cur_index]
        collisions = t.shape_item.collidingItems(Qt.IntersectsItemBoundingRect)
        colls = reduce(lambda x, y: x | y, [isinstance(c, Shape) for c in collisions])
        # move colls in the same direction as t was going, just a little bit
        # move self and family in opposite direction
        # - If colls in same family? Everything is one big family.
        # Colls cannot be between siblings by the nature of placement, unless moved by hand
        # This creates a problem. To what depth do you recurse while adjusting a tree?
        # - The solution like the rest of my implmentation lies in effective local data accumulation
        # - There should be dict which keeps track of subtrees, i.e.,
        #    - All thoughts are zero order subtrees
        #    - All parents and children are first order subtrees
        #    - All according to depth, locally
        #    - Higher order subtrees can be built with lower order subtrees with DP
        #    - Then collisions can be detected with subtree overlap
        #       - That is, if the collision is within the same first order subtree, then only adjust that
        #       - If collision is between two first order subtrees, only need to modify them
        #       - If one first order subtree collides with multiple first order subtrees, it gets more
        #         complicated.

        if colls:
            # This code will have to change substantially
            t_others = set.union(*[i for i in t.family[dir].values()])
            if len(t_others) == 1:
                # single child probably collided in the same direction it was added in
                # adjust in some direction yourself, no siblings
                pass
            else:
                # For not the first child, it probably collides to the side
                if t_others[0] == t.index:
                    t_other = self.thoughts[t_others[1]]
                else:
                    t_other = self.thoughts[t_others[0]]
                # need to use coo_x, y here
                diff = coo(t) - coo(t_other)
                if diff > 0:
                    self.move_in_dir(t_others, 'neg', self.orient_map[dir])
                else:
                    self.move_in_dir(t_others, 'pos', self.orient_map[dir])

    # to adjust thoughts, but can be a generic function to move
    # ts are indices
    def move_in_dir(self, ts, pos, orientation):
        direction = self.dir_map[pos][orientation]
        x, y = self.op_map[direction]
        for t in ts:
            self.thoughts[t].shape_item.moveBy(x, y)
        self.thoughts[self.thoughts[t].family['parent']].shape_item.moveBy(x/2, y/2)

    # sets the insert direction based on the key event for the thought,
    # according to which the future children will be added
    def set_insert_direction(self, event):
        direction = None
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_H:
            direction = 'l'
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_L:
            direction = 'r'
        elif event.key() == Qt.Key_Up or event.key() == Qt.Key_K:
            direction = 'u'
        elif event.key() == Qt.Key_Down or event.key() == Qt.Key_J:
            direction = 'd'

        selected = self.get_selected()
        for item in selected:
            arrow = Arrow(item, direction)
            self.arrows.append(arrow)
            self.scene.addItem(arrow)
            item.insert_dir = direction  # for now

    # This function is not used
    def remove_arrows(self):
        if self.arrows:
            direction = self.arrows[0].direction
            while self.arrows:
                self.scene.removeItem(self.arrows.pop())
            selected = self.get_selected()
            for item in selected:
                if isinstance(item, Shape):
                    item = item.text_item
                item.insert_dir = direction

    def key_navigate(self, event):
        # A lot of the code below may be redundant
        direction = None
        if event.key() == Qt.Key_Escape:
            self.unselect_all()
            self.toggle_nav_cycle(False)
            return
        elif event.key() == Qt.Key_Left or event.key() == Qt.Key_H:
            direction = 'l'
            ind = 0
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_L:
            direction = 'r'
            ind = 0
        elif event.key() == Qt.Key_Up or event.key() == Qt.Key_K:
            direction = 'u'
            ind = 1
        elif event.key() == Qt.Key_Down or event.key() == Qt.Key_J:
            direction = 'd'
            ind = 1
        movement = None
        if direction in {'l', 'r'}:
            movement = 'horizontal'
        else:
            movement = 'vertical'
        if self.cycle_items:
            retval = self.cycle_between(direction, movement, True)
            if not retval:
                return

        thoughts = self.get_selected()  # should be shapes instead of thoughts
        if not len(thoughts):
            self.select_one(1)
        if ind == 0:
            coo = self.coo_x
        elif ind == 1:
            coo = self.coo_y

        if len(thoughts) == 1:
            thought = None
            if isinstance(thoughts[0], Shape):
                thought = thoughts[0].text_item
            if thought.family[direction]:
                # print (thought.family[direction])
                # can be parent, children or siblings
                if 'parent' in thought.family[direction]:
                    self.select_one(thought.family[direction]['parent'])
                    event.accept()
                elif 'siblings' in thought.family[direction]:
                    print(thought.text, thought.family)
                    self.toggle_nav_cycle(True, movement, thought.family[direction]['siblings'], direction)
                elif 'children' in thought.family[direction]:
                    self.select_one(thought.family[direction]['children'])
        event.accept()

    def search_toggle(self):
        self.toggled_search = not self.toggled_search
        if self.toggled_search:
            # self.search_entry.place(x=0, y=pixelY-30, width=500, height=30)
            # gview = self.scene.views()[0]
            # self.search_widget.setPos(gview.mapToScene(gview.rect().topLeft()))
            self.search_widget.update_text()
            self.search_widget.setVisible(True)
            self.search_widget.setText("")
            self.search_widget.setFocus()
            self.typing = True
        else:
            self.toggle_search_cycle(toggle=False)
            self.search_widget.setVisible(False)
            self.typing = False
            self.un_highlight()

    def cycle_check(self, ind):
        if ind not in self.cycle_items:
            self.toggle_nav_cycle(False)

    def toggle_nav_cycle(self, toggle, movement=None, item_inds=None, direction=None):
        # items are always thoughts
        if toggle and not self.cycle_items and item_inds:
            print (movement)
            current_item = self.scene.selectedItems()[0]  # guaranteed to be one
            if isinstance(current_item, Thought):
                item_index = current_item.index
            else:
                item_index = current_item.text_item.index
            sorted_inds = None
            if movement == 'horizontal':
                sorted_inds = [(ind, self.coo_x(ind)) for ind in item_inds if self.thoughts[ind].isVisible()]
                sorted_inds.sort(key=lambda x: x[1])
                print (sorted_inds)
            elif movement == 'vertical':
                sorted_inds = [(ind, self.coo_y(ind)) for ind in item_inds if self.thoughts[ind].isVisible()]
                sorted_inds.sort(key=lambda x: x[1])
            self.cycle_items = [x[0] for x in sorted_inds]
            self.cycle_index = self.cycle_items.index(item_index)
            self.movement = movement
            if direction:
                self.cycle_between(direction, movement, True)
        elif not toggle and self.cycle_items:
            self.cycle_index = 0
            self.cycle_items = []


    def toggle_search_cycle(self, t_inds=None, toggle=True):
        if toggle:
            self.cycle_items = t_inds
            self.cycle_index = 0
            self.select_one(self.cycle_items[self.cycle_index])
        else:
            self.cycle_items = []

    def search_cycle(self, key):
        if key == Qt.Key_N:
            self.cycle_index = (self.cycle_index + 1) % len(self.cycle_items)
        elif key == Qt.Key_P:
            self.cycle_index = (self.cycle_index - 1) % len(self.cycle_items)
        self.select_one(self.cycle_items[self.cycle_index])

    def cycle_between(self, direction, movement=None, cycle=False):
        print (self.movement, movement)
        if not self.movement:
            self.movement = movement
            self.cycle_between(direction, movement, cycle=cycle)
        elif self.movement != movement:
            print (self.thoughts[self.cycle_items[self.cycle_index]].family[direction])
            if 'parent' in self.thoughts[self.cycle_items[self.cycle_index]].family[direction] or \
               'children' in self.thoughts[self.cycle_items[self.cycle_index]].family[direction]:
                self.movement = None
                self.cycle_items = []
                self.toggle_nav_cycle(False)
                return direction
            else:
                return
        # self.dir_map[
        else:
            if direction == self.dir_map[self.movement][0]:
                if not cycle:
                    self.cycle_index = max(0, self.cycle_index - 1)
                else:
                    self.cycle_index = (self.cycle_index - 1) % len(self.cycle_items)
            elif direction == self.dir_map[self.movement][1]:
                if not cycle:
                    self.cycle_index = min(len(self.cycle_items) - 1, self.cycle_index + 1)
                else:
                    self.cycle_index = (self.cycle_index + 1) % len(self.cycle_items)
            self.select_one(self.cycle_items[self.cycle_index])
            return None

    # def fix_expansion(self, thoughts, fix='part'):
    #     def temp(t):
    #         for c in ['u', 'd', 'l', 'r']:
    #             if t.part_expand[c] == 'e':
    #                 t.expand = 'e'
    #                 return True
    #     if isinstance(thoughts, Thought):
    #         thoughts = [thoughts]
    #     if fix == 'part':
    #         for t in thoughts:
    #             if not temp(t):
    #                 t.expand = 'd'
    #     elif fix == 'exp':
    #         for t in thoughts:
    #             if t.expand == 'd':
    #                 for c in ['u', 'd', 'l', 'r']:
    #                     t.part_expand[c] = 'd'

    # currently only expands a single node
    def partial_expand(self, event):
        selected = self.get_selected()
        if not len(selected) == 1:
            return
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_H:
            direction = 'l'
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_L:
            direction = 'r'
        elif event.key() == Qt.Key_Up or event.key() == Qt.Key_K:
            direction = 'u'
        elif event.key() == Qt.Key_Down or event.key() == Qt.Key_J:
            direction = 'd'

        for thought in selected:
            if isinstance(thought, Shape):
                thought = thought.text_item
            print ("part_expand", thought.text, thought.part_expand)
            if 'siblings' in thought.family[direction]:  # or 'siblings' in thought.family[self.inverse_map[direction]]:
                if thought.part_expand[direction] == 'e':
                    if 'children' in thought.family[direction]:  # and thought.family[direction]['children']:
                        self.select_one(thought.family[direction]['children'])
                        self.toggle_nav_cycle(False)
                        self.toggle_nav_cycle(True, item_inds=thought.family[direction]['children'],
                                              movement=self.inverse_orientmap[direction])
                    else:
                        print("not children, collapsing_opposite", direction, thought.part_expand)
                        thought.part_expand[direction] = 'd'
                        self.collapse_indir(thought, self.inverse_map[direction])
                elif 'children' in thought.family[direction]:
                    thought.part_expand[direction] = 'e'
                    self.expand_indir(thought, direction)
                else:
                    thought.part_expand[self.inverse_map[direction]] = 'd'
                    self.collapse_indir(thought, self.inverse_map[direction])
            else:
                if thought.part_expand[self.inverse_map[direction]] == 'e':
                    if 'children' in thought.family[self.inverse_map[direction]]:
                        thought.toggle_expand('d', self.inverse_map[direction])
                        self.collapse_indir(thought, self.inverse_map[direction])
                    else:
                        thought.toggle_expand('e', direction)
                        self.expand_indir(thought, direction)
                else:
                    if 'children' in thought.family[direction]:
                        thought.toggle_expand('e', direction)
                        self.expand_indir(thought, direction)
                    else:
                        thought.part_expand[self.inverse_map[direction]] = 'd'
                        self.collapse_indir(thought, self.inverse_map[direction])

    def collapse_indir(self, thought, direction):
        expansion = thought.toggle_expand('d', direction)
        print("collapsing", direction, thought.part_expand)
        self.hide_children(thought, expansion, direction)

    def expand_indir(self, thought, direction):
        expansion = thought.toggle_expand('e', direction)
        print("expanding", direction, thought.part_expand)
        self.hide_children(thought, expansion, direction)

    def check_hide_links(self, indices):
        if isinstance(indices, int):
            for k in self.links.keys():
                if indices in k:
                    self.links[k].setVisible(not self.thoughts[indices].hidden)
        else:  # assumes indices is a list
            for ind in indices:
                for k in self.links.keys():
                    if ind in k:
                        self.links[k].setVisible(not self.thoughts[ind].hidden)

    # for descendants one level deep
    def hide_children(self, thought, expansion, direction):
        if 'children' in thought.family[direction]:
            # if thought.family[direction]['children']:
            children = [self.thoughts[x] for x in thought.family[direction]['children']]
            for child in children:
                child.check_hide(False if expansion == 'e' else True)
                self.links[thought.index, child.index].setVisible(True if expansion == 'e' else False)
            # self.fix_expansion(children, 'part')
            self.hide_thoughts(children, expansion, True, False)


    def hide_thoughts(self, thoughts, expansion=None, recurse=False, expand_leaves=True):
        thoughts = [t if isinstance(t, Thought) else t.text_item for t in thoughts]
        # 'e' is expand, 'd' is hide
        for thought in thoughts:
            if not expansion:
                expansion = thought.toggle_expand('t')
            elif recurse:
                thought.toggle_expand(expansion)
            # print(thought.old_hidden, " " + expansion)
            children = [self.thoughts[i] for i in thought.family['children']]
            if expansion == 'e':
                for child in children:
                    if not expand_leaves:
                        thought.toggle_expand('d')
                        if child.family['children']:
                            child.check_hide(False)
                            self.links[thought.index, child.index].setVisible(True)
                            thought.toggle_expand('e')
                    else:
                        child.check_hide(False)
                        self.links[thought.index, child.index].setVisible(True)
                if recurse:
                    self.hide_thoughts(children, 'e', recurse=True, expand_leaves=expand_leaves)
                # self.adjust_thoughts()
            elif expansion == 'd':
                for child in children:
                    child.check_hide(True)
                    child.toggle_expand('d')
                    self.links[(thought.index, child.index)].setVisible(False)
                self.hide_thoughts(children, 'd')
        # self.fix_expansion(thoughts, 'exp')

    def other_key_events(self, event):
        if event.keysym == 'a':
            pass        # append node (at the same level of hierarchy)
        elif event.keysym == 'u':
            pass                # undo (that's a tough one)
        elif event.keysym == 'o':
            if response == 'yes':
                self.saveData(save_file)
            elif response == 'no':
                pass
                # filename = askopenfilename()
            elif response == 'cancel':
                pass

        # Maybe 'n' just makes a new sheet and doesn't kill the old sheet.
        # That I think is simpler since killing is fairly easy and that
        # should allow multiple mindmap objects and hence Sheets
        # to exist simultaneously
        elif event.keysym == 'n':
            if response == 'yes':
                self.saveData(save_file)
            elif response == 'no':
                if dir:
                    self.root_dir = dir
                self.canvas.destroy()
            elif response == 'cancel':
                pass
        elif event.keysym == 'S': # save_as
            self.saveData(self.filename)
