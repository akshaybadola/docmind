import sys

import numpy as np

from PyQt5.QtCore import Qt, QRectF, QPointF, QSize, QSizeF
from PyQt5.QtGui import (QBrush, QPainterPath, QPainter, QColor, QPen, QPixmap,
                         QRadialGradient, QMouseEvent, QKeyEvent)
from PyQt5.QtWidgets import (QGraphicsEllipseItem, QApplication, QGraphicsView,
                             QGraphicsRectItem, QGraphicsScene, QGraphicsItem,
                             QGraphicsTextItem, QGraphicsPixmapItem,
                             QGraphicsDropShadowEffect)
# from GraphicsView import GraphicsView

# so now most of the basic drawing is working. I don't need
# any animation for now and I've added the icon
# Need to add changed cursors for movement of the items

# text_rect = self.text_item.boundingRect().getRect()
# self.rect_ = QRectF(text_rect[0] - 10, text_rect[1] - 10, text_rect[2] + 20, text_rect[3] + 20)

Shapes = {'ellipse': 1, 'rectangle': 2, 'rounded_rectangle': 3, 'circle': 4}
class Shape(QGraphicsEllipseItem):
    # super(Shape, self).__init__(br)
    def __init__(self, text_item, color, *args):
        self.text_item = text_item
        self.family = self.text_item.family
        self.index = self.text_item.index
        self.color = color
        super(Shape, self).__init__(self.boundingRect())
        self.setFlags(
            self.flags() | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)   # | QGraphicsItem.ItemSendsScenePositionChanges)
        self.make_brush()
        self.prepareGeometryChange()
        self.set_editable = self.text_item.set_editable
        self.open_pdf = self.text_item.open_pdf
        self.setZValue(-1)
        self.text_item.mmap.links_zvalue(self.text_item, -2)

    # ['l', 'u', 'r', 'd']
    def get_link_coords(self):
        rect = self.boundingRect().getRect()
        return ((rect[0], rect[1] + rect[3]/2), (rect[0] + rect[2]/2, rect[1]),
                (rect[0] + rect[2], rect[1]+rect[3]/2), (rect[0] + rect[2]/2, rect[1] + rect[3]))

    def make_brush(self, brush_type='regular'):
        base_color = None
        if self.color == "red":
            base_color = [255, 0, 0, 255]
            mask = [0, 1.1, 1, 0]
        elif self.color == "blue":
            base_color = [20, 100, 255, 255]
            mask = [.8, .6, 0, 0]
            # mask = [.5, .5, 0, 0]
        elif self.color == "yellow":
            base_color = [240, 200, 0, 255]
            mask = [.06, .25, 1.25, 0]
        elif self.color == "green":
            base_color = [0, 240, 0, 255]
            mask = [1.1, .06, 1.2, 0]

        levels = None
        gd = QRadialGradient(self.boundingRect().center(), self.boundingRect().width())
        grad_colors = []
        if brush_type == 'dark':
            grad_colors.append([c + m * 180 for c, m in zip(base_color, mask)])
            grad_colors.append([c + m * 20 for c, m in zip(base_color, mask)])
        elif brush_type == 'regular':
            grad_colors.append([c + m * 20 for c, m in zip(base_color, mask)])
            grad_colors.append([c + m * 60 for c, m in zip(base_color, mask)])
            grad_colors.append([c + m * 100 for c, m in zip(base_color, mask)])
            grad_colors.append([c + m * 200 for c, m in zip(base_color, mask)])

        levels = len(grad_colors)
        positions = list(np.linspace(0, 1, levels))
        for i, p in enumerate(positions):
            gd.setColorAt(p, QColor(*grad_colors[i]))
        self.setBrush(QBrush(gd))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_editable(True)
            event.accept()

            # self.text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            # self.text_item.setFocus()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.text_item.mmap.update_pos()
        if change == QGraphicsItem.ItemSelectedChange:
            if value:
                self.setZValue(2)
                self.make_brush('dark')
                self.text_item.mmap.links_zvalue(self.text_item, 1)
                self.text_item.mmap.cycle_check(self.text_item.index)
            else:
                self.setZValue(-1)
                self.make_brush('regular')
                self.text_item.mmap.links_zvalue(self.text_item, -2)
        self.update()
        return super().itemChange(change, value)

    def to_pixmap(self):
        rect = self.boundingRect()
        pixmap = QPixmap(rect.size().toSize())  # , transformMode=Qt.SmoothTransformation)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        painter.translate(-rect.topLeft())
        self.paint(painter, None, None)
        painter.save()
        painter.setPen(QPen(Qt.black))
        painter.drawText(QPointF(10, 10), self.text_item.text)
        painter.drawPixmap(QPointF(-20, -20), self.text_item.pdf_icon(), QRectF(-8, -8, 40, 40))  # QRectF(-8,-8,16,16), self.text_item.pdf_icon())
        painter.restore()
        painter.end()
        return pixmap

# Must create similar classes like these
class Ellipse(Shape):
    def __init__(self, text_item, color, *args):
        # super().__init__(text_item, color, *args)
        super(Ellipse, self).__init__(text_item, color, *args)

    def boundingRect(self):
        text_rect = self.text_item.boundingRect().getRect()
        wid = text_rect[2]
        ht = text_rect[3]
        return QRectF(text_rect[0] - wid/6, text_rect[1] - ht/4, text_rect[2] + wid/3, text_rect[3] + ht/2)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(QPen(Qt.NoPen))
        # painter.setPen(QPen(QColor(0, 0, 0, 255), 0.0, Qt.SolidLine))
        painter.drawEllipse(self.boundingRect())


class Circle(Shape):
    def __init__(self, text_item, color, *args):
        # super().__init__(text_item, color, *args)
        super(Circle, self).__init__(text_item, color, *args)

    def boundingRect(self):
        # what if the height changes and not width? We need the larger of the two
        # And better would be if I find the center and then draw from it
        text_cent = self.text_item.boundingRect().center()
        text_rect = self.text_item.boundingRect().getRect()
        wid = text_rect[2] * 1.1
        ht = (0.35 * wid + text_rect[3]) * 1.1
        if wid > ht:
            met = wid
        else:
            met = ht
        return QRectF(text_cent.x() - met/2, text_cent.y() - met/2, met, met)
        # return QRectF(text_rect[0] - wid * 0.05, text_rect[1] - wid * 0.4, text_rect[3] + wid * 0.8, text_rect[3] + wid * 0.8)  # text_rect[2] + wid/3

    def shape(self):
        path = QPainterPath()
        path.addEllipse(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(QPen(Qt.NoPen))
        # painter.setPen(QPen(QColor(0, 0, 0, 255), 0.0, Qt.SolidLine))
        painter.drawEllipse(self.boundingRect())


class Rectangle(Shape):
    def __init__(self, text_item, color, *args):
        # super().__init__(text_item, color, *args)
        super(Rectangle, self).__init__(text_item, color, *args)

    def boundingRect(self):
        text_rect = self.text_item.boundingRect().getRect()
        # wid = text_rect[2]
        # ht = text_rect[3]
        return QRectF(text_rect[0] - 10, text_rect[1] - 10, text_rect[2] + 20, text_rect[3] + 20)
        # return QRectF(text_rect[0] - wid/6, text_rect[1] - ht/4, text_rect[2] + wid/3, text_rect[3] + ht/2)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(QPen(Qt.NoPen))
        # painter.setPen(QPen(QColor(0, 0, 0, 255), 0.0, Qt.SolidLine))
        painter.drawRect(self.boundingRect())

class RoundedRectangle(Shape):
    def __init__(self, text_item, color, *args):
        # super().__init__(text_item, color)
        super(RoundedRectangle, self).__init__(text_item, color, *args)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def boundingRect(self):
        text_rect = self.text_item.boundingRect().getRect()
        return QRectF(text_rect[0] - 10, text_rect[1] - 10, text_rect[2] + 20, text_rect[3] + 20)
        # side = self.text_item.side
        # wid = text_rect[2]
        # ht = text_rect[3]
        # if side == 'left':
        #     return QRectF(text_rect[0] - wid/6, text_rect[1] - ht/4, text_rect[2] + wid/3, text_rect[3] + ht/2)
        # elif side == 'right':
        #     return QRectF(text_rect[0] - wid/6, text_rect[1] - ht/4, text_rect[2] + wid/3, text_rect[3] + ht/2)
        # elif side == 'up':
        #     return QRectF(text_rect[0] - wid/6, text_rect[1] - ht/4, text_rect[2] + wid/3, text_rect[3] + ht/2)
        # elif side == 'down':
        #     return QRectF(text_rect[0] - wid/6, text_rect[1] - ht/4, text_rect[2] + wid/3, text_rect[3] + ht/2)
        # return QRectF(text_rect[0] - wid/6, text_rect[1] - ht/4, text_rect[2] + wid/3, text_rect[3] + ht/2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(QPen(Qt.NoPen))
        # painter.setPen(QPen(QColor(0, 0, 0, 255), 0.0, Qt.SolidLine))
        painter.drawRoundedRect(self.boundingRect(), 5.0, 5.0)


# class Icon(QGraphicsPixmapItem):
#     def __init__(self, pixmap, parent):
#         super(Icon, self).__init(pixmap, parent)


# def main():
#     app = QApplication(sys.argv)

#     grview = GraphicsView()
#     scene = QGraphicsScene()
#     scene.setSceneRect(0, 0, 680, 459)
#     scene.stickyFocus = True

#     scene.addPixmap(QPixmap('01.png'))
#     grview.setScene(scene)

#     st = ShapeType
#     # Shape = None
#     # item = Shape(None, 0, 0, 300, 150)
#     e_item = CustomTextItem("this is a text", st.oval)
#     e_item.add_item(scene, (10.0, 10.0))
#     r_item = CustomTextItem("this is a text", st.rectangle)
#     r_item.add_item(scene, (100.0, 100.0))
#     rr_item = CustomTextItem("this is a text", st.rounded_rectangle)
#     rr_item.add_item(scene, (200.0, 200.0))
#     c_item = CustomTextItem("this is a text", st.circle)
#     c_item.add_item(scene, (300.0, 300.0))
#     grview.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
#     grview.show()
#     sys.exit(app.exec_())


# main()
