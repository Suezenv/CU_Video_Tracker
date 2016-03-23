# -*- coding: utf-8 -*-
from PyQt4 import QtCore, QtGui
from qgis.core import *
from qgis.gui import *


###### THANKS TO VIDEO UAV TRACKER PLUGIN #################


class PositionMarker(QgsMapCanvasItem):
	""" marker for current GPS position """

	def __init__(self, canvas, alpha=255):
		QgsMapCanvasItem.__init__(self, canvas)
		self.pos = None
		self.hasPosition = False
		self.d = 20
		self.angle = 0
		self.setZValue(100) # must be on top
		self.alpha=alpha

	def newCoords(self, pos):
		if self.pos != pos:
			self.pos = QgsPoint(pos) # copy
			self.updatePosition()

	def setHasPosition(self, has):
		if self.hasPosition != has:
			self.hasPosition = has
			self.update()

	def updatePosition(self):
		if self.pos:
			self.setPos(self.toCanvasCoordinates(self.pos))
			self.update()

	def paint(self, p, xxx, xxx2):
		if not self.pos:
			return

		path = QtGui.QPainterPath()
		path.moveTo(0,7)
		path.lineTo(0,7)
		path.lineTo(5,5)
		path.lineTo(7,0)
		path.lineTo(5,-5)
		path.lineTo(0,-7)
		path.lineTo(-5,-5)
		path.lineTo(-7,0)
		path.lineTo(-5,5)
		path.lineTo(0,7)
		# render position with angle
		p.save()
		p.setRenderHint(QtGui.QPainter.Antialiasing)
		if self.hasPosition:
			p.setBrush(QtGui.QBrush(QtGui.QColor(255,0,0, self.alpha)))
		else:
			p.setBrush(QtGui.QBrush(QtGui.QColor(200,200,200, self.alpha)))
		p.setPen(QtGui.QColor(255,255,0, self.alpha))
		p.rotate(self.angle)
		p.drawPath(path)
		p.restore()

	def boundingRect(self):
		return QtCore.QRectF(-self.d,-self.d, self.d*2, self.d*2)

class ReplayPositionMarker(PositionMarker):
	def __init__(self, canvas):
		PositionMarker.__init__(self, canvas)

	def paint(self, p, xxx, xxx2):
		if not self.pos:
			return

		path = QtGui.QPainterPath()
		path.moveTo(0,7)
		path.lineTo(0,7)
		path.lineTo(5,5)
		path.lineTo(7,0)
		path.lineTo(5,-5)
		path.lineTo(0,-7)
		path.lineTo(-5,-5)
		path.lineTo(-7,0)
		path.lineTo(-5,5)
		path.lineTo(0,7)


		# render position with angle
		p.save()
		p.setRenderHint(QtGui.QPainter.Antialiasing)
		p.setBrush(QtGui.QBrush(QtGui.QColor(255,0,0)))
		p.setPen(QtGui.QColor(255,255,0))
		p.rotate(self.angle)
		p.drawPath(path)
		p.restore()
