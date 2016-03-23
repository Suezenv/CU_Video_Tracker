# -*- coding: utf-8 -*-


###### THANKS TO VIDEO UAV TRACKER PLUGIN #################


from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
import resources
from CanvasMarkers import *


class ReplayMapTool(QgsMapToolPan):
	"""
	Map tool that enables user interact with source plugins' canvas items,
	and if no source plugin "is interested", it allows convenient way of current
	recording position seeking by clicking on the recording gpx track on map. If
	the user clicks out of gpx track region, the map tool works as pan map tool.
	"""
	def __init__(self, canvas, Cu_Video_TrackerDialog):
		QgsMapToolPan.__init__(self, canvas)
		self.controller=Cu_Video_TrackerDialog
		self.posMarker=None
		self.rewinding=False

	def canvasPressEvent(self, mouseEvent):

		layerPt=self.canvasPointToRecordingLayerPoint(mouseEvent.pos().x(), mouseEvent.pos().y())


		if mouseEvent.button()==Qt.LeftButton:
			if self.trySnappingPosition(mouseEvent.pos().x(), mouseEvent.pos().y()):
				#click on the recorded track
				self.rewinding=True
			else:
				#otherwise use the qgis pan map tool
				QgsMapToolPan.canvasPressEvent(self, mouseEvent)
		elif mouseEvent.button()==Qt.RightButton:
			layerPoint = self.canvasPointToRecordingLayerPoint(mouseEvent.pos().x(), mouseEvent.pos().y())
			self.controller.AddPoint(layerPoint)


	def canvasMoveEvent(self, mouseEvent):
		if mouseEvent.buttons()&Qt.LeftButton and self.rewinding:
			if not self.trySnappingPosition(mouseEvent.pos().x(), mouseEvent.pos().y()):
				QgsMapToolPan.canvasMoveEvent(self, mouseEvent)
		else:
			QgsMapToolPan.canvasMoveEvent(self, mouseEvent)

	def canvasReleaseEvent(self, mouseEvent):
		if mouseEvent.button()&Qt.LeftButton and self.rewinding:
			#We were showing user target replay position, now do the real seek in recording
			#and discard the temporary canvas item
			self.trySnappingPosition(mouseEvent.pos().x(), mouseEvent.pos().y(), True)
			self.rewinding=False

			self.canvas().scene().removeItem(self.posMarker)
			self.posMarker=None

		QgsMapToolPan.canvasReleaseEvent(self, mouseEvent)

	def trySnappingPosition(self, x, y, doSeek=False):
		"""
		Try snapping the specified position to recorded track, and start displaying
		target seek postion/do the seek, depending on doSeek parameter.
		"""
		layerPoint=self.canvasPointToRecordingLayerPoint(x, y)

		self.controller.findNearestPointInRecording(layerPoint)


	def canvasPointToRecordingLayerPoint(self, x, y):
		mapPoint = self.canvas().getCoordinateTransform().toMapPoint(x, y)
		return self.canvas().mapRenderer().mapToLayerCoordinates(self.controller.CSVLayer, mapPoint)
