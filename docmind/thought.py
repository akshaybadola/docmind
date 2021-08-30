import subprocess
import math
import threading
import sys

import PIL
from PyQt5.QtCore import (qAbs, QLineF, QPointF, qrand, QRectF, QSizeF, qsrand,
                          Qt, QTime)
from PyQt5.QtGui import (QBrush, QPainterPath, QPainter, QColor, QPen, QFont,
                         QTextCursor, QPixmap, QRadialGradient, QMouseEvent,
                         QKeyEvent, QFontMetricsF, QTextDocument)
from PyQt5.QtWidgets import (QGraphicsEllipseItem,
                             QGraphicsRectItem,QGraphicsScene,
                             QGraphicsItemGroup, QGraphicsItem,
                             QGraphicsTextItem, QGraphicsSimpleTextItem,
                             QGraphicsPixmapItem, QGraphicsDropShadowEffect)
from Shape import Ellipse, Rectangle, RoundedRectangle, Circle, Shapes

# So, I've mostly separated the two parts, i.e., the textobject stuff
# and the thought stuff. It should work seamlessly.
class Thought(QGraphicsTextItem):
    # Class variables
    _mupdf = None
    _imsize = (16, 16)

    # shape_item is the reference to the item
    # item_shape is the type of shape it is
    # self.item = CustomTextItem(self.text, self.shape)
    # Color of the thought is controlled by the Brush of the shape_item
    def __init__(self, mmap, index, shape=None, coords=None, group=None, data={}, pdf='', text=''):
        super(Thought, self).__init__(text)
        self.mmap = mmap
        self.set_properties(index, shape, coords, data, pdf, text)
        self.set_variables()
        # print(self.qf.boundingRect(self.text).getRect())
        if not coords:
            print("cannot draw thought without position")
            return
        else:
            self.draw_thought()

    # def setBrush(self, brush):
    #     self.shape_item.setBrush(brush)

    # def pos(self):
        # rect_ = super(Thought, self).boundingRect().getRect()
        # return (super().pos().x() - rect_[2], rect_[0])

    # def setPos(self, pos):
    #     self.shape_item.prepareGeometryChange()
    #     super().setPos(pos[0], pos[1])

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    # Depending on the direction the thought is added, I only have to
    # change the sign in the thought item
    # width and height are in the bottom right diagonal as positive
    # Assumption is that they're added to the end of the groups
    # which is right and down
    def boundingRect(self):
        return super().boundingRect()
        # rect_ = super(Thought, self).boundingRect().getRect()
        # if self.side == 'left':
        #     return QRectF(rect_[0] - rect_[2], rect_[1], rect_[2], rect_[3])  # only invert x axis
        # elif self.side == 'right':
        #     return QRectF(rect_[0], rect_[1], rect_[2], rect_[3])  # normal
        # elif self.side == 'up':
        #     return QRectF(rect_[0], rect_[1] - rect_[3], rect_[2], rect_[3])  # only invert y axis
        # elif self.side == 'down':
        #     return QRectF(rect_[0], rect_[1], rect_[2], rect_[3])  # normal

    def focusInEvent(self, event):
        self.mmap.typing = True
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.text = self.toPlainText()
        ts = self.textCursor()
        ts.clearSelection()
        self.setTextCursor(ts)
        self.mmap.typing = False
        event.accept()  # super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or (event.key() == Qt.Key_G and event.modifiers() & Qt.ControlModifier):
            self.setTextInteractionFlags(Qt.NoTextInteraction)
            event.accept()
        else:
            super().keyPressEvent(event)

    def set_editable(self, editable=True):
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus()
        # cursor = self.textCursor()
        # cursor.select(cursor.Document)
        # cursor.movePosition(cursor.End)
        # print(cursor.selection().toPlainText())

    # I'll fix this later
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_editable(True)
            event.accept()

    def paint(self, painter, style, widget):
        self.shape_item.prepareGeometryChange()
        # painter.drawRect(self.boundingRect())
        # self.document().drawContents(painter, self.boundingRect())
        # painter.drawText(self.boundingRect(), self.document().toPlainText())
        # self.document().drawContents(painter, self.boundingRect())
        # This works now. After every paint() scene is also updated
        super().paint(painter, style, widget)
        self.mmap.scene.update()

    def draw_thought(self):
        self.prepareGeometryChange()
        scene = self.mmap.scene
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(10)
        self.shape_item.setGraphicsEffect(effect)
        scene.addItem(self)
        scene.addItem(self.shape_item)
        self.setParentItem(self.shape_item)
        rect_ = self.boundingRect().getRect()
        # now the thought is simply added on the left of the cursor
        if not self.shape_coords:
            if self.side == 'l':
                self.shape_item.setPos(self.mapFromScene(self.coords.x() - rect_[2], self.coords.y()))
            elif self.side == 'u':
                self.shape_item.setPos(self.mapFromScene(self.coords.x(), self.coords.y() - rect_[3]))
            else:
                self.shape_item.setPos(self.mapFromScene(self.coords.x(), self.coords.y()))
            self.shape_coords = (self.shape_item.pos().x(), self.shape_item.pos().y())
        else:
            self.shape_item.setPos(self.shape_coords[0], self.shape_coords[1])
        # I can paint this directly on to the ellipse also, I don't know which
        # will be faster, but then I'll have to calculate bbox while clicking
        pix = self.pdf_icon()
        if self.item_shape == Shapes['rectangle'] or self.item_shape == Shapes['rounded_rectangle']:
            self.icon = QGraphicsPixmapItem(pix, self.shape_item)
            self.icon.setPos(-20, -10)
            # scene.addItem(item.icon)
        elif self.item_shape == Shapes['ellipse']:
            self.icon = QGraphicsPixmapItem(pix, self.shape_item)
            self.icon.setPos(-16, -16)
        elif self.item_shape == Shapes['circle']:
            self.icon = QGraphicsPixmapItem(pix, self.shape_item)
            self.icon.setPos(-8, -24)
        self.handle_icon()
        self.icon.open_pdf = self.open_pdf
        # self.itemChange = self.shape_item_change
        self.setSelected = self.shape_item.setSelected
        self.check_hide(self.hidden)
        # self.icon.hoverEnterEvent = self.icon_hover_event
        # self.icon.hoverLeaveEvent = self.icon_hover_event
        # self.icon.mouseReleaseEvent = self.icon_release_event

    def to_pixmap(self):
        self.shape_item.to_pixmap()

    def handle_icon(self):
        if self.pdf:
            self.icon.setCursor(Qt.PointingHandCursor)
        else:
            self.icon.setCursor(Qt.ArrowCursor)

    def pdf_icon(self):
        if self.pdf:
            return self._color_file
        else:
            return self._grey_file

    def set_variables(self):
        self.shape_item = None
        if not self.item_shape:
            print("Please give a shape")
            sys.exit()
        if self.item_shape == Shapes['ellipse']:
            self.shape_item = Ellipse(self, self.color)
        elif self.item_shape == Shapes['rectangle']:
            self.shape_item = Rectangle(self, self.color)
        elif self.item_shape == Shapes['rounded_rectangle']:
            self.shape_item = RoundedRectangle(self, self.color)
        elif self.item_shape == Shapes['circle']:
            self.shape_item = Circle(self, self.color)
        else:
            print(self.item_shape, "Please give a valid shape")
            sys.exit()

        # This I'll have to check each time
        # self.selected = self.shape_item.isSelected
        self.content = self.text
        self.icon = None
        # Right now it's not passing control back to the parent
        # But multiple items move if I do control click
        # self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setDefaultTextColor(Qt.black)
        # self.setFlags(self.flags() | QGraphicsItem.ItemIsSelectable)

        self._color_file = QPixmap('icons/pdf.png').scaled(
            20, 20, aspectRatioMode=Qt.KeepAspectRatioByExpanding, transformMode=Qt.SmoothTransformation)
        self._grey_file = QPixmap('icons/pdfgrey.png').scaled(
            20, 20, aspectRatioMode=Qt.KeepAspectRatioByExpanding, transformMode=Qt.SmoothTransformation)
        self.focus_toggle = False
        self.old_coords = None
        self.insert_dir = 'u'
        # rect = self.shape_item.boundingRect().getRect()
        # Relative coords. left, up, right, down
        # self.shape_item.set_link_coords(
        #     ((rect[0], rect[1] + rect[3]/2), (rect[0] + rect[2]/2, rect[1]),
        #      (rect[0] + rect[2], rect[1]+rect[3]/2), (rect[0] + rect[2]/2, rect[1] + rect[3])))
        # self.nearest_child = {'pos': {'horizontal': None, 'vertical': None},
        # 'neg': {'horizontal': None, 'vertical': None}}

    def serialize(self):
        data = {}
        data['index'] = self.index
        data['coords'] = (self.coords.x(), self.coords.y())
        data['shape_coords'] = self.shape_coords
        data['text'] = self.text
        data['font_attribs'] = self.font_attribs
        data['pdf'] = self.pdf
        data['expand'] = self.expand
        data['part_expand'] = self.part_expand
        data['hidden'] = self.hidden
        data['hash'] = self.hash
        data['shape'] = self.item_shape
        data['color'] = self.color
        data['side'] = self.side

        # set is not serializable for some reason
        # May have to amend this later
        family_dict = {}
        for c in ['u', 'd', 'l', 'r']:
            if c in self.family.keys():
                family_dict[c] = {}
                for k, v in self.family[c].items():
                    family_dict[c][k] = list(v) if isinstance(v, set) else v
        family_dict['parent'] = self.family['parent']
        family_dict['children'] = list(self.family['children'])
        data['family'] = family_dict

        return data

    def set_properties(self, index, shape, coords, data, pdf, text):
        if shape not in Shapes.values():
            print("Invalid Shape")
            sys.exit()
        else:
            if 'shape' in data:
                self.item_shape = data['shape']
            else:
                self.item_shape = shape

        if 'index' in data:
            self.index = data['index']
        else:
            self.index = index

        # siblings aren't needed to be added, as they're in self.family[direction]
        # They are restored automatically from data{}
        self.family = {'u': {}, 'd': {}, 'l': {}, 'r': {},
                       'parent': None, 'children': set()}
        if 'family' in data:
            for c in ['u', 'd', 'l', 'r']:
                if c in data['family']:
                    for k, v in data['family'][c].items():
                        self.family[c][k] = set(v) if isinstance(v, list) else v
            self.family['parent'] = data['family']['parent']
            self.family['children'] = set(data['family']['children'])

        self.coords = coords
        if 'shape_coords' in data:
            self.shape_coords = data['shape_coords']
        else:
            self.shape_coords = None

        if 'text' in data:
            self.text = data['text']
            self.setPlainText(self.text)
        else:
            self.text = text

        # left right up down center, c being center, i.e., it is the center thought
        # right would be the most normal one, i.e., 'pos', 'horizontal'

        if 'font_attribs' in data:
            self.font_attribs = data['font_attribs']
        else:
            self.font_attribs = {'family': 'Calibri', 'point_size': 12}
            font = QFont()
            font.setFamily(self.font_attribs['family'])
            font.setPointSize(self.font_attribs['point_size'])
            self.setFont(font)

        if 'pdf' in data:
            pdf = data['pdf']
            self.pdf = pdf.replace('file://', '', 1) if pdf.startswith('file://') else pdf
        else:
            self.pdf = ""

        if 'hidden' in data:
            self.hidden = data['hidden']
        else:
            self.hidden = False
        self.old_hidden = self.hidden

        if 'hash' in data:
            self.hash = data['hash']
        else:
            self.hash = ""

        if 'side' in data:
            self.side = data['side']
        else:
            self.side = 'l'

        # expand 'e' for expand, 't' for toggle, 'd' for disabled
        if 'expand' in data:
            self.expand = data['expand']
        else:
            self.expand = 'e'

        if 'part_expand' in data:
            self.part_expand = data['part_expand']
        else:
            self.part_expand = {'u': 'e', 'd': 'e', 'l': 'e', 'r': 'e'}

        if 'color' in data:
            self.color = data['color']
        else:
            self.color = "red"

    def toggle_expand(self, expand, direction=None):
        if not direction:
            if expand == 't':
                if self.expand == 'e':
                    self.expand = 'd'
                else:
                    self.expand = 'e'
            else:
                self.expand = expand
            for i in self.part_expand.keys():
                self.part_expand[i] = self.expand
            return self.expand
        else:
            if expand == 't':
                if self.part_expand[direction] == 'e':
                    self.part_expand[direction] = 'd'
                else:
                    self.part_expand[direction] = 'e'
            else:
                self.part_expand[direction] = expand
            return self.part_expand[direction]

    def check_hide(self, hidden):
        if self.old_hidden != hidden:
            self.old_hidden = hidden
            self.hidden = hidden
        if self.hidden:
            self.hide()
        else:
            self.restore()

    def set_transluscent(self, opacity=0.7):
        self.shape_item.setOpacity(opacity)
        self.icon.setOpacity(opacity)
        self.setOpacity(opacity)

    def set_opaque(self):
        self.shape_item.setOpacity(1.0)
        self.icon.setOpacity(1.0)
        self.setOpacity(1.0)

    def update_parent(self, p_ind):
        pass

    # What about the links in the two functions below?
    # Must handle them
    def hide(self):
        self.setVisible(False)
        self.icon.setVisible(False)
        self.shape_item.setVisible(False)

    def restore(self):
        self.setVisible(True)
        self.icon.setVisible(True)
        self.shape_item.setVisible(True)

    def open_pdf(self):
        if self.pdf:
            self.mupdf = subprocess.Popen(['mupdf', self.pdf])

    def close_pdf(self):
        self.mupdf.kill()
        self.mupdf_lock = False

    def remove(self):
        self.mmap.scene.removeItem(self.shape_item)
        self.mmap.scene.removeItem(self.icon)
        self.mmap.scene.removeItem(self)

    # currently not supported
    def attach_pdf(self):
        print("trying to attach pdf")
