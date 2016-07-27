# -*- coding: utf-8 -*-
'''
**************************************************************************************************************************************
 CU_Video_Tracker                                                                                                                    *
                                 A QGIS plugin                                                                                       *
 This plugin display video with tracker
                              -------------------                                                                                    *
        begin                : 2016-03-23                                                                                            *
        copyright            : (C) 2016 by Suchawadee Sillaparat, Sanphet Chunithipaisan/ Department of Survey Engineering/
                               Chulalongkorn University/ Thailand                                                                    *
        email                : chadee.silla@hotmail.com,sanphet.c@chula.ac.th                                                        *
        website              : www.sv.eng.chula.ac.th                                                                                *
                                                                                                                                     *
This plugin is adapted and extended from Video UAV Tracker Plugin, written by Salvatore Agosta,                                      *
https://github.com/sagost/VideoUavTracker. And make use some part of Table Manager Plugin, written by Borys Jurgiel,                 *
https://github.com/borysiasty/tablemanager.                                                                                          *
Thanks to both plugins.                                                                                                              *
                                                                                                                                     *
**************************************************************************************************************************************

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
'''

# Import the PyQt and QGIS libraries
from PyQt4 import QtCore,QtGui, uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *

# Initialize Qt resources from file resources.py
import resources

# Import the code for the dialog
from cu_video_tracker_dialog_base import Ui_Form
from CanvasMarkers import PositionMarker
from CanvasMarkers import *
from ReplayMapTool import *


import datetime
import os
import osr           #from osgeo
import sys
import csv
import time

from PyQt4.phonon import Phonon

#TABLE MANAGER IMPORT
from tableManagerUi import Ui_Dialog
from tableManagerUiRename import Ui_Rename
from tableManagerUiClone import Ui_Clone
from tableManagerUiInsert import Ui_Insert

class Cu_Video_Tracker:
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = QFileInfo(QgsApplication.qgisUserDbFilePath()).path() + "/python/plugins/Cu_Video_Tracker"
        # initialize locale
        localePath = ""
        locale = str(QSettings().value("locale/userLocale"))[0:2]
        self.dlg = Cu_Video_TrackerDialog(iface)
        self.dlg.setWindowModality(QtCore.Qt.NonModal)
        self.dlg.setParent(self.iface.mainWindow(),QtCore.Qt.Dialog)

    def initGui(self):
        # Create action that will start plugin configuration
        self.action = QAction(
        QIcon(":/plugins/Cu_Video_Tracker/icon.png"), u"CU-Video Tracker", self.iface.mainWindow())
        # connect the action to the run method
        QObject.connect(self.action, SIGNAL("triggered()"), self.run)
        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&CU-GIS", self.action)

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&CU-Video Tracker", self.action)
        self.iface.removeToolBarIcon(self.action)

    # run method that performs all the real work
    def run(self):
        # show the dialog
        self.dlg.show()

class Cu_Video_TrackerDialog(QtGui.QDialog):
    def __init__(self, iface):
        QtGui.QDialog.__init__(self)
        # Set up the user interface from Designer.
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.iface = iface
        self.ui.sourceLoad_pushButton.clicked.connect(self.OpenButton)
        self.ui.replayPlay_pushButton.clicked.connect(self.PlayPauseButton)
        QObject.connect(self.ui.replay_mapTool_pushButton, SIGNAL("toggled(bool)"), self.replayMapTool_toggled)
        self.positionMarker=None
        settings = QSettings()
        settings.beginGroup("/plugins/PlayerPlugin")
        self.replay_followPosition = settings.value("followPosition", True, type=bool)
        settings.setValue("followPosition", self.replay_followPosition)

        QObject.connect(self.iface.mapCanvas(), SIGNAL("mapToolSet(QgsMapTool*)"), self.mapToolChanged)
        self.mapTool=ReplayMapTool(self.iface.mapCanvas(), self)
        self.mapTool_previous=None
        self.mapToolChecked = property(self.__getMapToolChecked, self.__setMapToolChecked)

        QObject.connect(self.ui.replayPosition_horizontalSlider, SIGNAL( 'sliderMoved(int)'), self.replayPosition_sliderMoved)
        QObject.connect(self.ui.addpoint_button, SIGNAL('clicked()'),self.snapshot)
        QObject.connect(self.ui.ExporText_button, SIGNAL('clicked()'),self.exportText)
        QObject.connect(self.ui.ExporShp_button, SIGNAL('clicked()'),self.exportShp)
        QObject.connect(self.ui.ExporSqlite_button, SIGNAL('clicked()'),self.exportSqlite)
        QObject.connect(self.ui.ExporKML_button, SIGNAL('clicked()'),self.exportKML)
        QObject.connect(self.ui.Help, SIGNAL('clicked()'),self.Help)

        self.PlayPuase = 0 # Puase=0,Play=1
        self.Close = 0 # select video=1 , Close=0
        self.adactProjection = False
        self.createLayer = 0 # Default layer=1,create by user=2,load existent=else
        self.videoWidget = Phonon.VideoWidget(self.ui.video_widget)

    def OpenButton(self):
        if self.Close == 1:
            if self.positionMarker != None:
                self.iface.mapCanvas().scene().removeItem(self.positionMarker)
                self.positionMarker = None
            self.Close = 0
            self.ui.replay_mapTool_pushButton.setChecked(False)
            self.ui.sourceLoad_pushButton.setText('Open...')
            self.createLayer = 0
            self.timer.stop()
            ##self.timer2.stop()
            self.media_obj.stop()
            self.iface.mapCanvas().unsetMapTool(self.mapTool)
            self.close()

        else:

            self.path = QtGui.QFileDialog.getOpenFileName(self,self.tr("Select Video files"))
            self.csvFile = open(self.path + '.csv',"rb")
            Filereader = csv.DictReader(self.csvFile)
            self.CSVLayer = QgsVectorLayer("LineString","GPS Tracking","memory")

            self.latt = []
            self.lonn = []
            self.timeh = []
            self.timem = []
            self.times = []
            i=0
            for row in Filereader:
                self.latt.append(float(row['lon']))
                self.lonn.append(float(row['lat']))
                if row['time_h'] != '':
                    self.timeh.append(int(row['time_h']))
                    self.timem.append(int(row['time_m']))
                    self.times.append(int(row['time_s']))

            #create tracker layer (line layer)
            for i in xrange(0,len(self.latt)-1,1):
                point_start = QgsPoint(self.latt[i],self.lonn[i])
                point_end = QgsPoint(self.latt[i+1],self.lonn[i+1])
                line = QgsGeometry.fromPolyline([point_start,point_end])
                self.pr = self.CSVLayer.dataProvider()
                afeature = QgsFeature()
                afeature.setGeometry(QgsGeometry.fromPolyline([point_start,point_end]))
                self.pr.addFeatures( [ afeature ] )
                self.CSVLayer.updateExtents()
            QgsMapLayerRegistry.instance().addMapLayers([self.CSVLayer])

            SelectLayer,ok = QInputDialog.getItem(self.iface.mainWindow(),"Layer chooser","Choose point layer",('Default point layer','Creat new point layer','Load existent point layer'))
            if SelectLayer == 'Load existent point layer':
                self.newLayerPath = QtGui.QFileDialog.getOpenFileName()
                if not self.newLayerPath is None:
                    name = self.newLayerPath.split("/")[-1][0:-4]
                    self.vl = QgsVectorLayer(self.newLayerPath, name, "ogr")
                    self.pr = self.vl.dataProvider()
                    fields = self.pr.fields()
                    field_names = [field.name() for field in fields]
                    f = "Image link"
                    fnd = self.vl.fieldNameIndex(f)
                    fn = field_names[fnd]
                    if not fn == f:
                        self.pr.addAttributes([QgsField("Image link", QVariant.String)])

                    QgsMapLayerRegistry.instance().addMapLayer(self.CSVLayer)
                    QgsMapLayerRegistry.instance().addMapLayer(self.vl)

            elif SelectLayer == 'Default point layer':
                self.vl = QgsVectorLayer("Point?crs=epsg:4326&index=yes","point", "memory")
                self.pr = self.vl.dataProvider()
                self.pr.addAttributes( [ QgsField('id', QVariant.Int),
                                         QgsField('Name', QVariant.String),
                                         QgsField('Description', QVariant.String),
                                         QgsField('Type', QVariant.String),
                                         QgsField("Lon",  QVariant.String),
                                         QgsField("Lat", QVariant.String),
                                         QgsField('East UTM', QVariant.String),
                                         QgsField('North UTM',QVariant.String),
                                         QgsField('Image link', QVariant.String)] )


                # update layer's extent
                self.vl.updateExtents()
                QgsMapLayerRegistry.instance().addMapLayer( self.CSVLayer )
                QgsMapLayerRegistry.instance().addMapLayers([self.vl])
                self.createLayer = 1

            else:
                # Creat new point layer by user
                self.createLayer = 2
                self.vl = QgsVectorLayer("Point?crs=epsg:4326&index=yes","point", "memory")
                self.pr = self.vl.dataProvider()
                # table manager dialog
                self.dialoga = TableManager(self.iface, self.vl,self.CSVLayer)
                self.dialoga.exec_()



            #set point label
            palyr = QgsPalLayerSettings()
            palyr.readFromLayer(self.vl)
            palyr.enabled = True
            palyr.fieldName = 'id'
            palyr.placement= QgsPalLayerSettings.Upright
            palyr.setDataDefinedProperty(QgsPalLayerSettings.Size,True,True,'14','')
            palyr.writeToLayer(self.vl)

            if self.positionMarker==None:
                self.positionMarker=PositionMarker(self.iface.mapCanvas())

            self.media_src = Phonon.MediaSource(self.path)
            self.media_obj = Phonon.MediaObject(self)
            self.media_obj.setCurrentSource(self.media_src)
            Phonon.createPath(self.media_obj, self.videoWidget)


            # set audio
##            audio_out = Phonon.AudioOutput(Phonon.VideoCategory, self)
##            Phonon.createPath(self.media_obj, audio_out)

            self.ui.video_widget.resizeEvent = self.Resize()
            self.media_obj.setTickInterval(100)
            self.timer = QtCore.QTimer()
            QtCore.QObject.connect(self.timer, QtCore.SIGNAL("timeout()"), self.Timer)

            self.PlayPuase =1
            self.ui.sourceLoad_pushButton.setText('Close')
            self.Close = 1   #load file selector
            self.media_obj.play()  #phonon play
            self.timer.start(1000)

            self.ui.replayPlay_pushButton.setEnabled(True)
            self.ui.addpoint_button.setEnabled(True)

    def Resize(self):
        a = self.ui.video_widget.frameSize()
        b = self.videoWidget.frameSize()
        if a != b:
            self.videoWidget.resize(a)

    def CurrentPos(self):
        end = self.media_obj.totalTime()
        pos = self.media_obj.currentTime()
        if pos == end:
            self.timer.stop()
            self.media_obj.pause()
            if self.PlayPuase == 1:
                self.PlayPuase = 0
        else:
            Pos = pos/1000
            self.ui.replayPosition_label.setText(str(datetime.timedelta(seconds=int(Pos))) + '/' + str(datetime.timedelta(seconds=(int(end/1000)))))
            return int(Pos)

    def Timer(self):
        if self.PlayPuase == 1:
            self.updateReplayPosition()
            self.SetSlide()
        else:
            pass

    def TimeOffset(self):
        self.current_second =[]
        self.time_offset =[]

        if self.timeh != []:
            for i in xrange(0,len(self.timeh),1):
                    h_second = int(self.timeh[i])*60*60
                    m_second = int(self.timem[i])*60
                    s_second = int(self.times[i])
                    c_second = h_second + m_second + s_second
                    self.current_second.append(c_second)
                    t_of = int(int(self.current_second[i]) -int(self.current_second[0]))
                    self.time_offset.append(t_of)
        else:
            #find time offset
            for i in xrange(0,len(self.latt),1):
                # Number of record in csv
                self.NumRec = len(self.latt)
                #create new list start at 0
                self.L_Num = range(len(self.latt))
                #time interval
                self.t_interval = ((self.media_obj.totalTime()/1000)/float(self.NumRec - 1))
                t_of = self.L_Num[i] * self.t_interval
                self.time_offset.append(t_of)
        return self.time_offset

    def updateReplayPosition(self):
        pos = self.CurrentPos()

        # find the nearest timestamp offset of position time in logging data
        TimeOffset = self.TimeOffset()
        i = min(range(len(TimeOffset)),key=lambda x: abs(TimeOffset[x]-((pos))))
        if pos-1 == (self.media_obj.totalTime()/1000-1):
            self.media_obj.stop()
        if pos - TimeOffset[i] == 0:
            self.lat_new = self.latt[i]
            self.lon_new = self.lonn[i]
        else:
            if pos < TimeOffset[i]:
                Dlat = self.latt[i]- self.latt[i-1]
                Dlon = self.lonn[i]- self.lonn[i-1]
                Dtime = TimeOffset[i] - TimeOffset[i-1]
            else:
                Dlat = self.latt[i+1]- self.latt[i]
                Dlon = self.lonn[i+1]- self.lonn[i]
                Dtime = TimeOffset[i+1] - TimeOffset[i]

            Dti = float(pos -TimeOffset[i])
            Dlat_i = Dlat*(Dti/Dtime)
            Dlon_i = Dlon*(Dti/Dtime)
            self.lat_new = self.latt[i]+ Dlat_i
            self.lon_new = self.lonn[i] + Dlon_i

        self.lat,self.lon = self.lat_new,self.lon_new
        self.Point = QgsPoint()
        self.Point.set(self.lat,self.lon)

        canvas = self.iface.mapCanvas()
        mapRenderer = canvas.mapRenderer()
        crsSrc = QgsCoordinateReferenceSystem(4326)    # WGS 84
        crsDest = mapRenderer.destinationCrs()

        xform = QgsCoordinateTransform(crsSrc, crsDest) #usage: xform.transform(QgsPoint)

        self.positionMarker.setHasPosition(True)
        self.Point = xform.transform(self.Point)
        self.positionMarker.newCoords(self.Point)

        if self.replay_followPosition:
            extent=self.iface.mapCanvas().extent()

        boundaryExtent=QgsRectangle(extent)
        boundaryExtent.scale(1.0)
        if not boundaryExtent.contains(QgsRectangle(self.Point, self.Point)):
            extentCenter= self.Point
            newExtent=QgsRectangle(extentCenter.x()-extent.width()/1.7,extentCenter.y()-extent.height()/1.7,extentCenter.x()+extent.width()/17,extentCenter.y()+extent.height()/1.7)
            self.iface.mapCanvas().setExtent(newExtent)
            self.iface.mapCanvas().refresh()

        East,North,alt = self.transform_wgs84_to_utm(self.lat_new,self.lon_new)
        self.ui.E.setText ('Easting : ' + str(East))
        self.ui.N.setText ('Northing : ' + str(North))
        self.ui.lat.setText ('Latitude : ' + str(self.lon_new))
        self.ui.lon.setText('Longitude : ' + str(self.lat_new))

    def PlayPauseButton(self):
        if self.PlayPuase == 1:
            self.media_obj.pause()
            self.timer.stop()
            self.PlayPuase = 0
        else:
            self.media_obj.play()
            self.timer.start(0)
            self.PlayPuase = 1

    def replayMapTool_toggled(self, checked):
        """Enable/disable replay map tool"""
        self.useMapTool(checked)

    def useMapTool(self, use):
        """ afer you click on it, you can seek the video just clicking on the gps track """

        if use:
            if self.iface.mapCanvas().mapTool()!=self.mapTool:
                self.mapTool_previous=self.iface.mapCanvas().mapTool()
                self.iface.mapCanvas().setMapTool(self.mapTool)
        else:
            if self.mapTool_previous!=None:
                self.iface.mapCanvas().setMapTool(self.mapTool_previous)
            else:
                self.iface.mapCanvas().unsetMapTool(self.mapTool)

    def mapToolChanged(self, tool):
        """Handle map tool changes outside  plugin"""
        if (tool!=self.mapTool) and self.mapToolChecked:
            self.mapTool_previous=None
            self.mapToolChecked=False

    def __getMapToolChecked(self):
        return self.replay_mapTool_pushButton.isChecked()

    def __setMapToolChecked(self, val):
        self.replay_mapTool_pushButton.setChecked(val)

    def findNearestPointInRecording(self, toPoint):
        """ Find the point nearest to the specified point (in map coordinates) """
        for i in xrange(0,len(self.latt),1):
            if(str(self.latt[i]))[0:7] == str(toPoint.x())[0:7]and (str(self.lonn[i]))[0:7]==(str(toPoint.y()))[0:7]:
                adj = (self.time_offset[i]) - (self.time_offset[0])
                lat,lon =(self.latt[i]) , (self.lonn[i])
                Point = QgsPoint()
                Point.set(lat,lon)
                self.positionMarker.newCoords(Point)
                self.Seek(adj)
                break

    def Seek (self, pos):
        if self.PlayPuase == 0:
            self.timer.stop()
            self.media_obj.seek(pos*1000)
            self.media_obj.play()
            self.timer.start(0)
            self.PlayPuase =1
        else:
            self.media_obj.seek(pos*1000)
            self.timer.start(1000)

    def replayPosition_sliderMoved(self,pos):
        """Handle moving of replay position slider by user"""
        self.Seek(pos)

    def SetSlide(self):
        end = self.media_obj.totalTime()
        pos = self.media_obj.currentTime()
        self.endtime = (self.media_obj.totalTime()/1000)
        self.ui.replayPosition_horizontalSlider.setMinimum(0)
        self.ui.replayPosition_horizontalSlider.setMaximum((self.endtime))
        if not pos == end:
            pos = float(self.CurrentPos())
            self.ui.replayPosition_horizontalSlider.setValue(pos)

    def AddPoint (self,toPoint):
        if self.PlayPuase == 1:
            self.media_obj.pause()
            self.timer.stop()
            self.PlayPuase = 0
        else:
            pass

        last_desc = '///'
        fc = int(self.pr.featureCount()+1)
        if self.createLayer == 1:
            self.vl.dataProvider()
            filename = self.path + '__'+ str(self.getImageFileName()) + '.jpg'
            p= QPixmap.grabWidget(self.videoWidget)
            p.save(filename)

            (Name,ok) = QInputDialog.getText(
                        self.iface.mainWindow(),
                        "Attributes",
                        "Name",
                        QLineEdit.Normal,
                        last_desc)

            (Description,ok) = QInputDialog.getText(
                         self.iface.mainWindow(),
                         "Attributes",
                         "Description",
                         QLineEdit.Normal,
                         last_desc)

            (Type,ok) = QInputDialog.getText(
                         self.iface.mainWindow(),
                         "Attributes",
                         "Type",
                         QLineEdit.Normal,
                         last_desc)

            # create the feature
            feature = QgsFeature()
            lat,lon = toPoint.x(), toPoint.y()
            Point = QgsPoint()
            Point.set(lat,lon)
            EastUTM,NorthUTM,alt= self.transform_wgs84_to_utm(lat, lon)
            feature.setGeometry(QgsGeometry.fromPoint(Point))

            feature.setAttributes([fc,Name,Description,Type,lat,lon,EastUTM,NorthUTM,self.path + '__'+ str(self.getImageFileName()) + '.jpg'])
            self.vl.startEditing()
            self.vl.addFeature(feature, True)
            self.vl.commitChanges()
            self.vl.setCacheImage(None)
            self.vl.triggerRepaint()
            os.rename(filename,self.path + '__'+ str(self.getImageFileName()) + '.jpg')

        elif self.createLayer == 2:
            p= QPixmap.grabWidget(self.videoWidget)
            fields = self.pr.fields()
            attributes = []
            lat,lon = toPoint.x(), toPoint.y()
            for field in fields:
                    a = str(field.name())
                    b = str(field.typeName())
                    if a == 'id':
                        fcnr = fc
                        attributes.append(fcnr)
                    elif a == 'Lon':
                        attributes.append(lat)

                    elif a == 'Lat':
                        attributes.append(lon)

                    else:

                        if b == 'String':
                            (a,ok) = QInputDialog.getText(
                                                          self.iface.mainWindow(),
                                                          "Attributes",
                                                          a + ' = ' + b,
                                                          QLineEdit.Normal)
                            attributes.append(a)


                        elif b == 'Real':
                            (a,ok) = QInputDialog.getDouble(
                                                            self.iface.mainWindow(),
                                                            "Attributes",
                                                            a + ' = ' + b, decimals = 10)
                            attributes.append(a)

                        elif b == 'Integer':
                            (a,ok) = QInputDialog.getInt(
                                                         self.iface.mainWindow(),
                                                         "Attributes",
                                                         a + ' = ' + b)
                            attributes.append(a)

            feature = QgsFeature()
            Point = QgsPoint()
            Point.set(lat,lon)

            #use in new table
            filename = self.path + '__'+ str(self.getImageFileName()) + '.jpg'
            p.save(filename)
            attributes.append(filename)
            feature.setGeometry(QgsGeometry.fromPoint(Point))
            feature.setAttributes(attributes)
            self.vl.startEditing()
            self.vl.addFeature(feature, True)
            self.vl.commitChanges()
            self.vl.setCacheImage(None)
            self.vl.triggerRepaint()
            os.rename(filename,self.path + '__'+ str(self.getImageFileName()) + '.jpg')

        else:

            p= QPixmap.grabWidget(self.videoWidget)

            fields = self.pr.fields()
            attributes = []
            lat,lon = toPoint.x(), toPoint.y()
            for field in fields:
                    a = str(field.name())
                    b = str(field.typeName())
                    if a == 'id':
                        fcnr = fc
                        attributes.append(fcnr)
                    elif a == 'Lon':
                        attributes.append(lat)

                    elif a == 'Lat':
                        attributes.append(lon)

                    else:

                        if b == 'String':
                            (a,ok) = QInputDialog.getText(
                                                          self.iface.mainWindow(),
                                                          "Attributes",
                                                          a + ' = ' + b,
                                                          QLineEdit.Normal)
                            attributes.append(a)


                        elif b == 'Real':
                            (a,ok) = QInputDialog.getDouble(
                                                            self.iface.mainWindow(),
                                                            "Attributes",
                                                            a + ' = ' + b, decimals = 10)
                            attributes.append(a)

                        elif b == 'Integer':
                            (a,ok) = QInputDialog.getInt(
                                                         self.iface.mainWindow(),
                                                         "Attributes",
                                                         a + ' = ' + b)
                            attributes.append(a)

            feature = QgsFeature()
            Point = QgsPoint()
            Point.set(lat,lon)
            #use in existent table
            feature.setGeometry(QgsGeometry.fromPoint(Point))
            feature.setAttributes(attributes)
            filename = self.path + '__'+ str(self.getImageFileName()) + '.jpg'
            p.save(filename)
            field_index = self.pr.fieldNameIndex('Image link')
            feature.setAttribute(field_index, filename)
            self.vl.startEditing()
            self.vl.addFeature(feature, True)
            self.vl.commitChanges()
            self.vl.setCacheImage(None)
            self.vl.triggerRepaint()
            os.rename(filename,self.path + '__'+ str(self.getImageFileName()) + '.jpg')

        self.ui.ExporText_button.setEnabled(True)
        self.ui.ExporShp_button.setEnabled(True)
        self.ui.ExporSqlite_button.setEnabled(True)
        self.ui.ExporKML_button.setEnabled(True)


    def getImageFileName(self):

        current_time_now = time.time()
        ctn_int = int(current_time_now)
        return ctn_int


    def transform_wgs84_to_utm(self, lon, lat):
        def get_utm_zone(longitude):
            return (int(1+(longitude+180.0)/6.0))

        def is_northern(latitude):
            """
            Determines if given latitude is a northern for UTM
            """

            if (latitude < 0.0):
                return 0
            else:
                return 1

        utm_coordinate_system = osr.SpatialReference()
        utm_coordinate_system.SetWellKnownGeogCS("WGS84") # Set geographic coordinate system to handle lat/lon
        utm_coordinate_system.SetUTM(get_utm_zone(lon), is_northern(lat))

        wgs84_coordinate_system = utm_coordinate_system.CloneGeogCS() # Clone ONLY the geographic coordinate system

        # create transform component
        wgs84_to_utm_transform = osr.CoordinateTransformation(wgs84_coordinate_system, utm_coordinate_system) # (<from>, <to>)
        return wgs84_to_utm_transform.TransformPoint(lon, lat, 0) # returns easting, northing, altitude

    def snapshot(self):
        Point = QgsPoint(self.Point)
        Point.set(self.lat,self.lon)
        self.positionMarker.newCoords(Point)
        self.AddPoint(Point)

    def Help(self):
        path_help = 'C:/Users/Administrator/.qgis2'
        os.startfile(path_help + '/python/plugins/Cu_Video_Tracker/How to.pdf')

    def exportText(self):
        toCSV = QgsVectorFileWriter.writeAsVectorFormat(self.vl, self.path + '_''point'+'.csv', "TIS-620", None, "CSV")
        debug = self.path + '_''point'+'.csv'
        QtGui.QMessageBox.information(self, 'Export to', debug )

    def exportShp(self):
        toShp = QgsVectorFileWriter.writeAsVectorFormat(self.vl, self.path + '_''point'+'.shp',"utf-8",None,"ESRI Shapefile")
        debug = self.path + '_''point'+'.shp'
        QtGui.QMessageBox.information(self, 'Export to', debug )

    def exportSqlite(self):
        toSql = QgsVectorFileWriter.writeAsVectorFormat(self.vl, self.path + '_''point'+'.sqlite',"utf-8",None,"SQLite")
        debug = self.path + '_''point'+'.sqlite'
        QtGui.QMessageBox.information(self, 'Export to', debug )

    def exportKML(self):
        toSql = QgsVectorFileWriter.writeAsVectorFormat(self.vl, self.path + '_''point'+'.kml',"utf-8",None,"KML")
        debug = self.path + '_''point'+'.kml'
        QtGui.QMessageBox.information(self, 'Export to', debug )

##############CLASS DialogRename##############################

class DialogRename(QDialog, Ui_Rename):
    def __init__(self, iface, fields, selection):
        QDialog.__init__(self)
        self.iface = iface
        self.setupUi(self)
        self.fields = fields
        self.selection = selection
        self.setWindowTitle(self.tr('Rename field: {0}').format(fields[selection].name()))
        self.lineEdit.setValidator(QRegExpValidator(QRegExp('[\w\ _]{,10}'),self))
        self.lineEdit.setText(fields[selection].name())
    def accept(self):
        if self.newName() == self.fields[self.selection].name():
            QDialog.reject(self)
            return

        for i in self.fields.values():
            if self.newName().upper() == i.name().upper() and i != self.fields[self.selection]:
                QMessageBox.warning(self,self.tr('Rename field'),self.tr('There is another field with the same name.\nPlease type different one.'))
                return

            if not self.newName():
                QMessageBox.warning(self,self.tr('Rename field'),self.tr('The new name cannot be empty'))
                self.lineEdit.setText(self.fields[self.selection].name())
                return
            QDialog.accept(self)
    def newName(self):
        return self.lineEdit.text()

########## CLASS DialogClone ##############################

class DialogClone(QDialog, Ui_Clone):
  def __init__(self, iface, fields, selection):
    QDialog.__init__(self)
    self.iface = iface
    self.setupUi(self)
    self.fields = fields
    self.selection = selection
    self.setWindowTitle(self.tr('Clone field: ')+fields[selection].name())
    self.comboDsn.addItem(self.tr('at the first position'))
    for i in range(len(fields)):
      self.comboDsn.addItem(self.tr('after the {0} field').format(fields[i].name()))
    self.comboDsn.setCurrentIndex(selection+1)
    self.lineDsn.setValidator(QRegExpValidator(QRegExp('[\w\ _]{,10}'),self))
    self.lineDsn.setText(fields[selection].name()[:8] + '_2')

  def accept(self):
    if not self.result()[1]:
      QMessageBox.warning(self,self.tr('Clone field'),self.tr('The new name cannot be empty'))
      return
    if self.result()[1] == self.fields[self.selection].name():
        QMessageBox.warning(self,self.tr('Clone field'),self.tr('The new field\'s name must be different then source\'s one!'))
        return
    for i in self.fields.values():
      if self.result()[1].upper() == i.name().upper():
        QMessageBox.warning(self,self.tr('Clone field'),self.tr('There is another field with the same name.\nPlease type different one.'))
        return
    QDialog.accept(self)

  def result(self):
    return self.comboDsn.currentIndex(), self.lineDsn.text()

########## CLASS DialogInsert ##############################

class DialogInsert(QDialog, Ui_Insert):
  def __init__(self, iface, fields, selection):
    QDialog.__init__(self)
    self.iface = iface
    self.setupUi(self)
    self.fields = fields
    self.selection = selection
    self.setWindowTitle(self.tr('Insert field'))
    self.lineName.setValidator(QRegExpValidator(QRegExp('[\w\ _]{,10}'),self))
    self.comboType.addItem(self.tr('Integer'))
    self.comboType.addItem(self.tr('Real'))
    self.comboType.addItem(self.tr('String'))
    self.comboPos.addItem(self.tr('at the first position'))
    for i in range(len(fields)):
      self.comboPos.addItem(self.tr('after the {0} field').format(fields[i].name()))
    self.comboPos.setCurrentIndex(selection+1)

  def accept(self):
    if not self.result()[0]:
      QMessageBox.warning(self,self.tr('Insert new field'),self.tr('The new name cannot be empty'))
      return
    for i in self.fields.values():
      if self.result()[0].upper() == i.name().upper():
        QMessageBox.warning(self,self.tr('Insert new field'),self.tr('There is another field with the same name.\nPlease type different one.'))
        return
    QDialog.accept(self)

  def result(self):
    return self.lineName.text(), self.comboType.currentIndex(), self.comboPos.currentIndex()


########## CLASS TableManager ##############################

class TableManager(QDialog, Ui_Dialog):

  def __init__(self, iface, vl,CSVLayer):
    QDialog.__init__(self)
    self.iface = iface
    self.setupUi(self)
    self.layer = vl
    self.CSVLayer = CSVLayer
    self.provider = self.layer.dataProvider()
    self.fields = self.readFields( self.provider.fields() )
    self.isUnsaved = False  # No unsaved changes yet
    if self.provider.storageType() == 'ESRI Shapefile': # Is provider saveable?
      self.isSaveable = True
    else:
      self.isSaveable = False

    self.needsRedraw = True # Preview table is redrawed only on demand. This is for initial drawing.
    self.lastFilter = None
    self.selection = -1     # Don't highlight any field on startup
    self.selection_list = [] #Update: Santiago Banchero 09-06-2009

    QObject.connect(self.butUp, SIGNAL('clicked()'), self.doMoveUp)
    QObject.connect(self.butDown, SIGNAL('clicked()'), self.doMoveDown)
    QObject.connect(self.butDel, SIGNAL('clicked()'), self.doDelete)
    QObject.connect(self.butIns, SIGNAL('clicked()'), self.doInsert)
    QObject.connect(self.butClone, SIGNAL('clicked()'), self.doClone)
    QObject.connect(self.butRename, SIGNAL('clicked()'), self.doRename)
    QObject.connect(self.butSaveAs, SIGNAL('clicked()'), self.doSaveAs)
    QObject.connect(self.fieldsTable, SIGNAL('itemSelectionChanged ()'), self.selectionChanged)
    QObject.connect(self.tabWidget, SIGNAL('currentChanged (int)'), self.drawDataTable)

    self.setWindowTitle(self.tr('Table Manager: {0}').format(self.layer.name()))

    self.drawFieldsTable()
    self.readData()


  def readFields(self, providerFields): # Populates the self.fields dictionary with providerFields
    fieldsDict = {}
    i=0
    for field in providerFields:
        fieldsDict.update({i:field})
        i+=1
    return fieldsDict

  def drawFieldsTable(self): # Draws the fields table on startup and redraws it when changed
    fields = self.fields
    self.fieldsTable.setRowCount(0)
    for i in range(len(fields)):
      self.fieldsTable.setRowCount(i+1)
      item = QTableWidgetItem(fields[i].name())
      item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
      item.setData(Qt.UserRole, i) # set field index
      self.fieldsTable.setItem(i,0,item)
      item = QTableWidgetItem(fields[i].typeName())
      item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
      self.fieldsTable.setItem(i,1,item)
    self.fieldsTable.setColumnWidth(0, 128)
    self.fieldsTable.setColumnWidth(1, 64)

  def readData(self): # Reads data from the 'provider' QgsDataProvider into the 'data' list [[column1] [column2] [column3]...]
    fields = self.fields
    self.data = []
    for i in range(len(fields)):
      self.data += [[]]
    steps = self.provider.featureCount()
    stepp = steps / 10
    if stepp == 0:
      stepp = 1
    progress = self.tr('Reading data ') # As a progress bar is used the main window's status bar, because the own one is not initialized yet
    n = 0
    for feat in self.provider.getFeatures():
        attrs = feat.attributes()

        for i in range(len(attrs)):
            self.data[i] += [attrs[i]]
        n += 1
        if n % stepp == 0:
            progress += '|'
            self.iface.mainWindow().statusBar().showMessage(progress)
    self.iface.mainWindow().statusBar().showMessage('')

  def drawDataTable(self,tab): # Called when user switches tabWidget to the Table Preview
    if tab != 1 or self.needsRedraw == False: return
    fields = self.fields
    self.dataTable.clear()
    self.repaint()
    self.dataTable.setColumnCount(len(fields))
    self.dataTable.setRowCount(self.provider.featureCount())
    header = []
    for i in fields.values():
      header.append(i.name())
    self.dataTable.setHorizontalHeaderLabels(header)
    formatting = True
    if formatting: # slower procedure, with formatting the table items
      for i in range(len(self.data)):
        for j in range(len(self.data[i])):
          item = QTableWidgetItem(unicode(self.data[i][j] or 'NULL'))
          item.setFlags(Qt.ItemIsSelectable)
          if fields[i].type() == 6 or fields[i].type() == 2:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
          self.dataTable.setItem(j,i,item)
    else: # about 25% faster procedure, without formatting
      for i in range(len(self.data)):
        for j in range(len(self.data[i])):
          self.dataTable.setItem(j,i,QTableWidgetItem(unicode(self.data[i][j] or 'NULL')))
    self.dataTable.resizeColumnsToContents()
    self.needsRedraw = False

  def setChanged(self): # Called after making any changes
    if self.isSaveable:
      self.butSave.setEnabled(True)
    self.butSaveAs.setEnabled(True)
    self.isUnsaved = True       # data are unsaved
    self.needsRedraw = True     # preview table needs to redraw

  def selectionChanged(self): # Called when user is changing field selection of field
    #self.selection_list = [ i.topRow() for i in self.fieldsTable.selectedRanges() ]
    self.selection_list = [i for i in range(self.fieldsTable.rowCount()) if self.fieldsTable.item(i,0).isSelected()]
    if len(self.selection_list)==1:
        self.selection = self.selection_list[0]
    else:
        self.selection = -1
    self.butDel.setEnabled( len(self.selection_list)>0 )

    item = self.selection
    if item == -1:
      self.butUp.setEnabled(False)
      self.butDown.setEnabled(False)
      self.butRename.setEnabled(False)
      self.butClone.setEnabled(False)
    else:
      if item == 0:
        self.butUp.setEnabled(False)
      else:
        self.butUp.setEnabled(True)
      if item == self.fieldsTable.rowCount()-1:
        self.butDown.setEnabled(False)
      else:
        self.butDown.setEnabled(True)
      if self.fields[item].type() in [2,6,10]:
         self.butRename.setEnabled(True)
         self.butClone.setEnabled(True)
      else:
        self.butRename.setEnabled(False)
        self.butClone.setEnabled(False)

  def doMoveUp(self): # Called when appropriate button was pressed
    item = self.selection
    tmp = self.fields[item]
    self.fields[item] = self.fields[item-1]
    self.fields[item-1] = tmp
    for i in range(0,2):
      tmp = QTableWidgetItem(self.fieldsTable.item(item,i))
      self.fieldsTable.setItem(item,i,QTableWidgetItem(self.fieldsTable.item(item-1,i)))
      self.fieldsTable.setItem(item-1,i,tmp)
    if item > 0:
      self.fieldsTable.clearSelection()
      self.fieldsTable.setCurrentCell(item-1,0)
    tmp = self.data[item]
    self.data[item]=self.data[item-1]
    self.data[item-1]=tmp
    self.setChanged()

  def doMoveDown(self): # Called when appropriate button was pressed
    item = self.selection
    tmp = self.fields[item]
    self.fields[self.selection] = self.fields[self.selection+1]
    self.fields[self.selection+1] = tmp
    for i in range(0,2):
      tmp = QTableWidgetItem(self.fieldsTable.item(item,i))
      self.fieldsTable.setItem(item,i,QTableWidgetItem(self.fieldsTable.item(item+1,i)))
      self.fieldsTable.setItem(item+1,i,tmp)
    if item < self.fieldsTable.rowCount()-1:
      self.fieldsTable.clearSelection()
      self.fieldsTable.setCurrentCell(item+1,0)
    tmp = self.data[item]
    self.data[item]=self.data[item+1]
    self.data[item+1]=tmp
    self.setChanged()

  def doRename(self): # Called when appropriate button was pressed
    dlg = DialogRename(self.iface,self.fields,self.selection)
    if dlg.exec_() == QDialog.Accepted:
      newName = dlg.newName()
      self.fields[self.selection].setName(newName)
      item = self.fieldsTable.item(self.selection,0)
      item.setText(newName)
      self.fieldsTable.setItem(self.selection,0,item)
      self.fieldsTable.setColumnWidth(0, 128)
      self.fieldsTable.setColumnWidth(1, 64)
      self.setChanged()

  def doDelete(self): # Called when appropriate button was pressed
    #<---- Update: Santiago Banchero 09-06-2009 ---->
    #self.selection_list = sorted(self.selection_list,reverse=True)
    all_fields_to_del = [self.fields[i].name() for i in self.selection_list if i <> -1]
    warning = self.tr('Are you sure you want to remove the following fields?\n{0}').format(", ".join(all_fields_to_del))
    if QMessageBox.warning(self, self.tr('Delete field'), warning , QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
        return
    self.selection_list.sort(reverse=True) # remove them in reverse order to avoid index changes!!!
    for r in self.selection_list:
        if r <> -1:
            del(self.data[r])
            del(self.fields[r])
            self.fields = dict(zip(range(len(self.fields)), self.fields.values()))
            self.drawFieldsTable()
            self.setChanged()

    self.selection_list = []
    #</---- Update: Santiago Banchero 09-06-2009 ---->

  def doInsert(self): # Called when appropriate button was pressed
    dlg = DialogInsert(self.iface,self.fields,self.selection)
    if dlg.exec_() == QDialog.Accepted:
      (aName, aType, aPos) = dlg.result()
      if aType == 0:
        aLength = 10
        aPrec = 0
        aVariant = QVariant.Int
        aTypeName = 'Integer'
      elif aType == 1:
        aLength = 32
        aPrec = 3
        aVariant = QVariant.Double
        aTypeName = 'Real'
      else:
        aLength = 80
        aPrec = 0
        aVariant = QVariant.String
        aTypeName = 'String'
      self.data += [[]]
      if aPos < len(self.fields):
        fieldsToMove = range(aPos+1,len(self.fields)+1)
        fieldsToMove.reverse()
        for i in fieldsToMove:
          self.fields[i] = self.fields[i-1]
          self.data[i] = self.data[i-1]
      self.fields[aPos] = QgsField(aName, aVariant, aTypeName, aLength, aPrec, "")
      aData = []
      if aType == 2:
        aItem = None
      else:
        aItem = None
      for i in range(len(self.data[0])):
        aData += [aItem]
      self.data[aPos] = aData
      self.drawFieldsTable()
      self.fieldsTable.setCurrentCell(aPos,0)
      self.setChanged()

  def doClone(self): # Called when appropriate button was pressed
    dlg = DialogClone(self.iface,self.fields,self.selection)
    if dlg.exec_() == QDialog.Accepted:
      (dst, newName) = dlg.result()
      self.data += [[]]
      movedField = QgsField(self.fields[self.selection])
      movedData = self.data[self.selection]
      if dst < len(self.fields):
        fieldsToMove = range(dst+1,len(self.fields)+1)
        fieldsToMove.reverse()
        for i in fieldsToMove:
          self.fields[i] = self.fields[i-1]
          self.data[i] = self.data[i-1]
      self.fields[dst] = movedField
      self.fields[dst].setName(newName)
      self.data[dst] = movedData
      self.drawFieldsTable()
      self.fieldsTable.setCurrentCell(dst,0)
      self.setChanged()

  def doSaveAs(self): # write data to memory layer
    #QgsMapLayerRegistry.instance().removeAllMapLayers()
    # create destination layer
    fields = QgsFields()
    keys = self.fields.keys()
    keys.sort()
    for key in keys:
        fields.append(self.fields[key])
    qfields = []
    for field in fields:
        qfields.append(field)
    self.provider.addAttributes([QgsField('id', QVariant.Int)])
    self.provider.addAttributes(qfields)
    self.provider.addAttributes([QgsField("Lon",QVariant.String),QgsField("Lat",QVariant.String),QgsField('Image link',QVariant.String)])
    self.layer.updateExtents()
    QgsMapLayerRegistry.instance().addMapLayer( self.CSVLayer )
    QgsMapLayerRegistry.instance().addMapLayer( self.layer )
    QgsProject.instance().dirty( True )
    self.close()
