import sys

from PyQt5.QtOpenGL import QGL
from PyQt5.QtOpenGL import QGLWidget
from PyQt5.QtOpenGL import QGLFormat

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QPainter
from PyQt5.QtWidgets import QGraphicsView, QApplication, QGraphicsScene, QGraphicsPixmapItem

# from MMap import MMap
from Thought import Thought
from Shape import Shape

# class MMap:
#     def __init__(self):
#         pass
#     def add_thought(self, pos):
#         print ("trying to add thought at ", pos)
# class MMLayout(QGridLayout):
class GraphicsView(QGraphicsView):
    def __init__(self, scene, mmap, parent=None):
        super(GraphicsView, self).__init__(scene, parent)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._isPanning = False
        self._mousePressed = False
        self._mousePressedRight = False
        self._positions = []
        self.setRenderHint(QPainter.Antialiasing)
        self.mmap = mmap
        # Zoom Factor
        self.zoomInFactor = 1.25
        self.zoomOutFactor = 1 / self.zoomInFactor
        # self.mmap = MMap(scene)

    def resizeEvent(self, event):
        self.mmap.reposition_status_bar(self.geometry())
        super().resizeEvent(event)

    def dragEnterEvent(self, event):
        accepted = False
        mime = event.mimeData()
        self.dragOver = True
        if mime.hasUrls():
            filepath = str(mime.urls()[0].toString())
            # check extension
            if filepath.split('.')[-1].lower() == 'pdf':
                accepted = True
        event.setAccepted(accepted)
        self.scene().update()

    def dragMoveEvent(self, event):
        pass

    def dragLeaveEvent(self, event):
        self.dragOver = True
        self.update()

    def dropEvent(self, event):
        self.dragOver = True
        self.mmap.drag_and_drop(
            event, self.mapToScene(event.pos()), pdf=str(event.mimeData().urls()[0].toString()))

    # All this still doesn't work perfectly but is better
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.modifiers() & Qt.ShiftModifier:
            self._mousePressed = True
            self.setCursor(Qt.ClosedHandCursor)
            self._dragPos = event.pos()
            event.accept()
        elif event.button() == Qt.RightButton:
            self._selected = self.mmap.get_selected()
            self._mousePressedRight = True
            self._dragPos = self.mapToScene(event.pos())
            if self._selected:
                self.mmap.try_attach_children(event, self._selected, 'begin')
            self._positions = [s.pos() for s in self._selected]
            event.accept()
        elif self.itemAt(event.pos()):
            item = self.itemAt(event.pos())
            if isinstance(item, Thought):
                if item.hasFocus():
                    pass
            else:
                self.mmap.text_uneditable_all()
            super(GraphicsView, self).mousePressEvent(event)
        else:
            self.mmap.text_uneditable_all()
            super(GraphicsView, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._mousePressedRight:
            print(self.mapToScene(event.pos()), event.pos().x(), event.pos().y(), self._dragPos.x(), self._dragPos.y())
            len(self._positions)
            diff = self.mapToScene(event.pos()) - self._dragPos
            if (self._selected):
                for i, item in enumerate(self._selected):
                    item.setPos(self._positions[i].x() + diff.x(), self._positions[i].y() + diff.y())
                self.mmap.try_attach_children(event, None, 'dragging')
            event.accept()
        if self._mousePressed and event.modifiers() & Qt.ShiftModifier:  # and event.button == Qt.LeftButton:
            newPos = event.pos()
            diff = newPos - self._dragPos
            self._dragPos = newPos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - diff.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - diff.y())
            event.accept()
        else:
            super(GraphicsView, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, QGraphicsPixmapItem):
            item.open_pdf()
            self._mousePressed = False
        if event.button() == Qt.RightButton and self._mousePressedRight:
           self.scene().clearSelection()
           self._mousePressedRight = False
           self.mmap.try_attach_children(event, None, 'end')
        elif event.button() == Qt.LeftButton and event.modifiers() & Qt.ShiftModifier:
            self._mousePressed = False
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
            self._mousePressed = False
            super(GraphicsView, self).mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.itemAt(event.pos()):
                self.mmap.add_thought(self.mapToScene(event.pos()))
            else:
                # send event to item
                item = self.itemAt(event.pos())
                if isinstance(item, Shape) or isinstance(item, Thought):
                    item.mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        # I also want shift to show me an insert direction
        if event.key() == Qt.Key_Plus and event.modifiers() & Qt.ControlModifier:
            self.scale(self.zoomInFactor, self.zoomInFactor)
        elif event.key() == Qt.Key_Minus and event.modifiers() & Qt.ControlModifier:
            self.scale(self.zoomOutFactor, self.zoomOutFactor)
        if event.key() == Qt.Key_Shift and not self._mousePressed:
            self._isPanning = True
            self.setCursor(Qt.OpenHandCursor)
        elif not self.mmap.typing:  # All the key events handled by the scene go here
            if event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
                self.mmap.select_all()
            if event.key() == Qt.Key_N and event.modifiers() & Qt.ShiftModifier:  # maybe change this later
                selected = self.scene().selectedItems()
                self.mmap.select_descendants(selected)
            if event.key() == Qt.Key_S:
                if event.modifiers() & Qt.ControlModifier:
                    self.mmap.search_toggle()
                else:
                    self.mmap.save_data()
                event.accept()
            if event.key() == Qt.Key_P or event.key() == Qt.Key_Return:  # open_pdf
                items = self.scene().selectedItems()
                if len(items) == 1 and (
                        isinstance(items[0], Thought) or isinstance(items[0], Shape)):
                    items[0].open_pdf()
                    event.accept()
                else:
                    super(GraphicsView, self).keyPressEvent(event)
            elif event.key() == Qt.Key_Space and event.modifiers() & Qt.ShiftModifier:  # recursive expansion
                self.mmap.hide_thoughts(self.mmap.get_selected(), 'e', recurse=True)
                event.accept()
            elif event.key() == Qt.Key_Space:  # expansion
                self.mmap.hide_thoughts(self.mmap.get_selected())
                event.accept()
            elif event.key() == Qt.Key_I:  # insertion
                thoughts = self.mmap.get_selected()
                if len(thoughts) == 1:
                    self.mmap.add_new_child(thoughts[0])
                elif not thoughts:
                    self.mmap.add_thought(QPointF(1.0, 1.0))
                event.accept()
            elif event.key() == Qt.Key_E:  # set editable
                items = self.scene().selectedItems()
                if len(items) == 1 and (
                        isinstance(items[0], Thought) or isinstance(items[0], Shape)):
                    items[0].set_editable(True)
                    event.accept()
                else:
                    super(GraphicsView, self).keyPressEvent(event)
            elif event.key() == Qt.Key_D:
                thoughts = self.mmap.get_selected()
                if thoughts:
                    for t in thoughts:
                        if isinstance(t, Thought):
                            self.mmap.delete_thought(t)
                        elif isinstance(t, Shape):
                            self.mmap.delete_thought(t.text_item)
            elif event.key() in {Qt.Key_H, Qt.Key_L, Qt.Key_K, Qt.Key_J, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down}:
                if event.modifiers() & Qt.ControlModifier:
                    self.mmap.partial_expand(event)  # or select children in that direction
                elif event.modifiers() & Qt.ShiftModifier:
                    self.mmap.set_insert_direction(event)
                else:
                    self.mmap.key_navigate(event)
                event.accept()
            elif event.key() == Qt.Key_Escape or ((event.key() == Qt.Key_G) and event.modifiers() & Qt.ControlModifier):
                self.mmap.unselect_all()
                event.accept()
        # This is when either the QGraphicsTextItem or the QLineEdit have focus
        else:
            super(GraphicsView, self).keyPressEvent(event)


    def keyReleaseEvent(self, event):
        # if any keyrelease happens, remove all arrows
        # Though, this is more of a hack.
        self.mmap.remove_arrows()
        if event.key() == Qt.Key_Shift:
            if not self._mousePressed:
                self._isPanning = False
                self.setCursor(Qt.ArrowCursor)
        else:
            super(GraphicsView, self).keyPressEvent(event)

    def wheelEvent(self, event):
        # Set Anchors
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        # Save the scene pos
        oldPos = self.mapToScene(event.pos())

        # Zoom
        if event.angleDelta().y() > 0:
            zoomFactor = self.zoomInFactor
        else:
            zoomFactor = self.zoomOutFactor
        self.scale(zoomFactor, zoomFactor)

        # Get the new position
        newPos = self.mapToScene(event.pos())

        # Move scene to old position
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())
        self.scene().update()


# app = QApplication(sys.argv)
# scene = QGraphicsScene()
# grview = GraphicsView(scene)
# grview.setCacheMode(grview.CacheBackground)
# grview.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
# grview.setViewport(QGLWidget(QGLFormat(QGL.SampleBuffers)))
# grview.resize(800, 600)
# scene.setSceneRect(0, 0, 800, 600)
# scene.stickyFocus = True
# grview.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
# grview.show()
# sys.exit(app.exec_())
