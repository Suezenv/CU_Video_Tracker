# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Cu_Video_Tracker
                                 A QGIS plugin
 This plugin display video with tracker
                             -------------------
        begin                : 2016-03-23
        copyright            : (C) 2016 by Suchawadee Sillaparat and
                               Sanphet Chunithipaisan
        email                : chadee.silla@hotmail.com,sanphet.c@chula.ac.th
        website              : www.sv.eng.chula.ac.th                                                                                *
                                                                                                                                     *
This plugin is adapted and extended from Video UAV Tracker Plugin, written by
Salvatore Agosta, https://github.com/sagost/VideoUavTracker. And make use some
part of Table Manager Plugin, written by Borys Jurgiel, https://github.com/
borysiasty/tablemanager.                                                                                          *
Thanks to both plugins.

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""



def classFactory(iface):  # pylint: disable=invalid-name
    """Load Cu_Video_Tracker class from file Cu_Video_Tracker.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .cu_video_tracker import Cu_Video_Tracker
    return Cu_Video_Tracker(iface)
