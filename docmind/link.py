import math
import threading

from PyQt5.QtCore import Qt, QRectF, QSizeF, QPointF, QLineF
from PyQt5.QtGui import QBrush, QPainterPath, QPainter, QColor, QPen, QPixmap, QRadialGradient, QPolygonF
from PyQt5.QtWidgets import QGraphicsLineItem, QGraphicsItem, QGraphicsDropShadowEffect
# Give all links in a family the same color and different
# colors for each parent/child relationship, perhaps lighter?
# Also, have the same level of line thickness for each member
# of hierarchy
from .thought import Thought

# start_item, end_item are Thought instances
class Arrow(QGraphicsLineItem):
    def __init__(self, item, direction, parent=None, scene=None, collide=False):
        super(Arrow, self).__init__(parent)
        self.arrowHead = QPolygonF()
        self.arrowHead = QPolygonF()
        self.collide = collide
        if isinstance(item, Thought):
            self.item = item.shape_item
        else:
            self.item = item
        self.color = QColor(80, 90, 100, 100)
        self.direction = direction
        self.setPen(QPen(self.color, 10, Qt.DashLine, Qt.SquareCap, Qt.MiterJoin))

    def setColor(self, color):
        self.color = color

    def boundingRect(self):
        extra = (self.pen().width() + 20) / 2.0
        p1 = self.line().p1()
        p2 = self.line().p2()
        return QRectF(p1, QSizeF(p2.x() - p1.x(), p2.y() - p1.y())).normalized().adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path = super(Arrow, self).shape()
        path.addPolygon(self.arrowHead)
        return path

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        color = self.color
        pen = self.pen()
        pen.setColor(self.color)
        arrowSize = 10.0
        painter.setPen(pen)
        painter.setBrush(self.color)
        # bottom point of first thought and top point of second thought
        # set according to direction from parent to child
        link_coords = self.item.get_link_coords()
        item_rect = self.item.boundingRect().getRect()
        if self.direction == 'l':
            # big hack, because in this case the coords were wrong, simply wrong
            # no idea why
            st = self.mapFromItem(self.item, link_coords[0][0], link_coords[1][1] + item_rect[3]/2)
            en = self.mapFromItem(self.item, link_coords[0][0] - 100, link_coords[1][1] + item_rect[3]/2)
        elif self.direction == 'r':
            st = self.mapFromItem(self.item, link_coords[2][0], link_coords[2][1])
            en = self.mapFromItem(self.item, link_coords[2][0] + 100, link_coords[2][1])
        elif self.direction == 'u':
            st = self.mapFromItem(self.item, link_coords[1][0], link_coords[1][1])
            en = self.mapFromItem(self.item, link_coords[2][0] - item_rect[2]/2, link_coords[2][1] - 100 - item_rect[3]/2)
        elif self.direction == 'd':
            st = self.mapFromItem(self.item, link_coords[3][0], link_coords[3][1])
            en = self.mapFromItem(self.item, link_coords[2][0] - item_rect[2]/2, link_coords[2][1] + 100 + item_rect[3]/2)

        line = self.setLine(QLineF(en, st))
        line = self.line()

        angle = math.acos(line.dx() / line.length())
        if line.dy() >= 0:
            angle = (math.pi * 2.0) - angle

        arrowP1 = line.p1() + QPointF(math.sin(angle + math.pi / 3.0) * arrowSize,
                                      math.cos(angle + math.pi / 3) * arrowSize)
        arrowP2 = line.p1() + QPointF(math.sin(angle + math.pi - math.pi / 3.0) * arrowSize,
                                      math.cos(angle + math.pi - math.pi / 3.0) * arrowSize)

        self.arrowHead.clear()
        for point in [line.p1(), arrowP1, arrowP2]:
            self.arrowHead.append(point)

        painter.drawLine(line)
        painter.drawPolygon(self.arrowHead)

        if self.isSelected():
            painter.setPen(QPen(color, 1, Qt.DashLine))
            myLine = QLineF(line)
            myLine.translate(0, 4.0)
            painter.drawLine(myLine)
            myLine.translate(0, -8.0)
            painter.drawLine(myLine)


class Link(QGraphicsLineItem):
    def __init__(self, start_item, end_item, color, parent=None, scene=None, direction=None, collide=False):
        super(Link, self).__init__(parent)
        self.arrowHead = QPolygonF()
        self.collide = collide
        if isinstance(start_item, Thought):
            self.start_item = start_item.shape_item  # actual boundary is of shape_item
        else:
            self.start_item = start_item
        if isinstance(end_item, Thought):
            self.end_item = end_item.shape_item
        else:
            self.end_item = end_item
        self.setColor(color)
        if not direction:
            self.direction = 'l'
        else:
            self.direction = direction
        if self.collide:
            self.setPen(QPen(self.color, 10, Qt.DotLine, Qt.RoundCap,
                             Qt.RoundJoin))
        else:
            self.setPen(QPen(self.color, 2, Qt.SolidLine, Qt.RoundCap,
                             Qt.RoundJoin))

    def setColor(self, color):
        if isinstance(color, str):
            if color == "red":
                base_color = [255, 0, 0, 255]
            elif color == "blue":
                base_color = [20, 100, 255, 255]
            elif color == "yellow":
                base_color = [240, 200, 0, 255]
            elif color == "green":
                base_color = [0, 240, 0, 255]
            self.color = QColor(*base_color)
        else:
            self.color = color

    def boundingRect(self):
        extra = (self.pen().width() + 20) / 2.0
        p1 = self.line().p1()
        p2 = self.line().p2()
        return QRectF(p1, QSizeF(p2.x() - p1.x(), p2.y() - p1.y())).normalized().adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path = super(Link, self).shape()
        path.addPolygon(self.arrowHead)
        return path

    # def updatePosition(self):
    #     self.graphicsEffect().updateBoundingRect()
    #     self.graphicsEffect().update()
    #     line = QLineF(self.mapFromItem(self.start_item, 0, 0), self.mapFromItem(self.end_item, 0, 0))
    #     self.setLine(line)
    #     self.update()

    def paint(self, painter, option, widget=None):
        if not self.collide:
            if (self.start_item.collidesWithItem(self.end_item)):
                return
        painter.setRenderHint(QPainter.Antialiasing)
        si = self.start_item
        ei = self.end_item
        color = self.color
        pen = self.pen()
        pen.setColor(self.color)
        arrowSize = 10.0
        painter.setPen(pen)
        painter.setBrush(self.color)

        # NOTE: It actually should be the the nearest path between two
        #       QPainterPaths. I think this code is trying to find the
        #       intersection between the line and the polygon, LOL

        # startpos = myStartItem.pos()
        # endpos = myEndItem.pos()
        # p1 = ep.first() + ei.pos()
        # ep = ei.shape().toFillPolygon()
        # start_poly = si.shape().toFillPolygon()
        # end_poly = ei.shape().toFillPolygon()
        # p1 = QPointF()
        # p2 = QPointF()
        # p_1 = QPointF()
        # p_2 = QPointF()
        # min_len = 100000000
        # for i in start_poly:
        #     p1 = si.pos() + i
        #     for j in end_poly:
        #         p2 = ei.pos() + j
        #         polyLine = QLineF(p1, p2)
        #         if polyLine.length() < min_len:
        #             p_1 = p1
        #             p_2 = p2

        # self.setLine(QLineF(p_1, p_2))
        # line = self.line()

        # centerLine = QLineF(myStartItem.pos(), myEndItem.pos())
        # endPolygon = myEndItem.shape().toFillPolygon()
        # p1 = endPolygon.first() + myEndItem.pos()

        # intersectPoint = QPointF()
        # for i in endPolygon:
        #     p2 = i + myEndItem.pos()
        #     polyLine = QLineF(p1, p2)
        #     intersectType = polyLine.intersect(centerLine, intersectPoint)
        #     if intersectType == QLineF.BoundedIntersection:
        #         break
        #     p1 = p2

        # self.setLine(QLineF(intersectPoint, myStartItem.pos()))
        # line = self.line()

        # bottom point of first thought and top point of second thought
        # set according to direction from parent to child
        if not self.collide:
            si_link_coords = si.get_link_coords()
            ei_link_coords = ei.get_link_coords()
            si_rect = si.boundingRect().getRect()
            if self.direction == 'l':
                # big hack, because in this case the coords were wrong, simply wrong
                # no idea why
                st = self.mapFromItem(si, si_link_coords[0][0], si_link_coords[1][1] + si_rect[3]/2)
                en = self.mapFromItem(ei, ei_link_coords[2][0], ei_link_coords[2][1])
            elif self.direction == 'r':
                st = self.mapFromItem(si, si_link_coords[2][0], si_link_coords[2][1])
                en = self.mapFromItem(ei, ei_link_coords[0][0], ei_link_coords[0][1])
            elif self.direction == 'u':
                st = self.mapFromItem(si, si_link_coords[1][0], si_link_coords[1][1])
                en = self.mapFromItem(ei, ei_link_coords[3][0], ei_link_coords[3][1])
            elif self.direction == 'd':
                st = self.mapFromItem(si, si_link_coords[3][0], si_link_coords[3][1])
                en = self.mapFromItem(ei, ei_link_coords[1][0], ei_link_coords[1][1])
        else:
            st = self.mapFromItem(si, si.boundingRect().center())
            en = self.mapFromItem(ei, ei.boundingRect().center())
        line = self.setLine(QLineF(en, st))
        line = self.line()

        angle = math.acos(line.dx() / line.length())
        if line.dy() >= 0:
            angle = (math.pi * 2.0) - angle

        arrowP1 = line.p1() + QPointF(math.sin(angle + math.pi / 3.0) * arrowSize,
                                      math.cos(angle + math.pi / 3) * arrowSize)
        arrowP2 = line.p1() + QPointF(math.sin(angle + math.pi - math.pi / 3.0) * arrowSize,
                                      math.cos(angle + math.pi - math.pi / 3.0) * arrowSize)

        self.arrowHead.clear()
        for point in [line.p1(), arrowP1, arrowP2]:
            self.arrowHead.append(point)

        painter.drawLine(line)
        painter.drawPolygon(self.arrowHead)

        if self.isSelected():
            painter.setPen(QPen(color, 1, Qt.DashLine))
            myLine = QLineF(line)
            myLine.translate(0, 4.0)
            painter.drawLine(myLine)
            myLine.translate(0, -8.0)
            painter.drawLine(myLine)
