# -*- coding: utf-8 -*-
# Reference:
# http://wiki.xbmc.org/index.php?title=Audio/Video_plugin_tutorial
import sys
import os
import urllib
import urlparse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson


__addon__ = xbmcaddon.Addon(id='script.videoextras')
__icon__ = __addon__.getAddonInfo('icon')
__fanart__ = __addon__.getAddonInfo('fanart')
__cwd__ = __addon__.getAddonInfo('path').decode("utf-8")
__profile__ = xbmc.translatePath(__addon__.getAddonInfo('profile')).decode("utf-8")
__resource__ = xbmc.translatePath(os.path.join(__cwd__, 'resources').encode("utf-8")).decode("utf-8")
__lib__ = xbmc.translatePath(os.path.join(__resource__, 'lib').encode("utf-8")).decode("utf-8")


sys.path.append(__resource__)
sys.path.append(__lib__)

# Import the common settings
from settings import Settings
from settings import log
from settings import os_path_join
from settings import dir_exists

# Load the database interface
from database import ExtrasDB

# Load the core Video Extras classes
from core import VideoExtrasBase

# Load the Video Extras Player that handles playing the extras files
from ExtrasPlayer import ExtrasPlayer

# Load any common dialogs
from dialogs import VideoExtrasResumeWindow


###################################################################
# Class to handle the navigation information for the plugin
###################################################################
class MenuNavigator():
    MOVIES = Settings.MOVIES
    TVSHOWS = Settings.TVSHOWS
    MUSICVIDEOS = Settings.MUSICVIDEOS

    def __init__(self, base_url, addon_handle):
        self.base_url = base_url
        self.addon_handle = addon_handle

    # Creates a URL for a directory
    def _build_url(self, query):
        return self.base_url + '?' + urllib.urlencode(query)

    # Display the default list of items in the root menu
    def showRootMenu(self):
        # Movies
        url = self._build_url({'mode': 'folder', 'foldername': MenuNavigator.MOVIES})
        li = xbmcgui.ListItem(__addon__.getLocalizedString(32110), iconImage=__icon__)
        li.setProperty("Fanart_Image", __fanart__)
        li.addContextMenuItems([], replaceItems=True)
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=url, listitem=li, isFolder=True)

        # TV Shows
        url = self._build_url({'mode': 'folder', 'foldername': MenuNavigator.TVSHOWS})
        li = xbmcgui.ListItem(__addon__.getLocalizedString(32111), iconImage=__icon__)
        li.setProperty("Fanart_Image", __fanart__)
        li.addContextMenuItems([], replaceItems=True)
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=url, listitem=li, isFolder=True)

        # Music Videos
        url = self._build_url({'mode': 'folder', 'foldername': MenuNavigator.MUSICVIDEOS})
        li = xbmcgui.ListItem(__addon__.getLocalizedString(32112), iconImage=__icon__)
        li.setProperty("Fanart_Image", __fanart__)
        li.addContextMenuItems([], replaceItems=True)
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=url, listitem=li, isFolder=True)

        xbmcplugin.endOfDirectory(self.addon_handle)

    # Show the list of videos in a given set
    def showFolder(self, foldername):
        # Check for the special case of manually defined folders
        if foldername == MenuNavigator.TVSHOWS:
            self.setVideoList('GetTVShows', MenuNavigator.TVSHOWS, 'tvshowid')
        elif foldername == MenuNavigator.MOVIES:
            self.setVideoList('GetMovies', MenuNavigator.MOVIES, 'movieid')
        elif foldername == MenuNavigator.MUSICVIDEOS:
            self.setVideoList('GetMusicVideos', MenuNavigator.MUSICVIDEOS, 'musicvideoid')

    # Produce the list of videos and flag which ones have themes
    def setVideoList(self, jsonGet, target, dbid):
        videoItems = self.getVideos(jsonGet, target, dbid)

        for videoItem in videoItems:
            if not self.hasVideoExtras(target, videoItem['dbid'], videoItem['file']):
                continue
            # Create the list-item for this video
            li = xbmcgui.ListItem(videoItem['title'], iconImage=videoItem['thumbnail'])
            # Remove the default context menu
            li.addContextMenuItems([], replaceItems=True)
            # Get the title of the video owning the extras
            parentTitle = ""
            try:
                parentTitle = videoItem['title'].encode("utf-8")
            except:
                log("setVideoList: failed to encode parent title %s" % parentTitle)

            # Set the background image
            if videoItem['fanart'] is not None:
                li.setProperty("Fanart_Image", videoItem['fanart'])
            else:
                videoItem['fanart'] = ""
            url = self._build_url({'mode': 'listextras', 'foldername': target, 'path': videoItem['file'].encode("utf-8"), 'parentTitle': parentTitle, 'defaultFanArt': videoItem['fanart'], 'defaultIconImage': videoItem['thumbnail']})
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=url, listitem=li, isFolder=True)

        xbmcplugin.endOfDirectory(self.addon_handle)

    # Do a lookup in the database for the given type of videos
    def getVideos(self, jsonGet, target, dbid):
        json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.%s", "params": {"properties": ["title", "file", "thumbnail", "fanart"], "sort": { "method": "title" } }, "id": 1}' % jsonGet)
        json_query = unicode(json_query, 'utf-8', errors='ignore')
        json_response = simplejson.loads(json_query)
        log(json_response)
        Videolist = []
        if ("result" in json_response) and (target in json_response['result']):
            for item in json_response['result'][target]:
                videoItem = {}
                videoItem['title'] = item['title']
                # The file is actually the path for a TV Show, the video file for movies
                videoItem['file'] = item['file']

                if item['thumbnail'] is None:
                    item['thumbnail'] = 'DefaultFolder.png'
                else:
                    videoItem['thumbnail'] = item['thumbnail']
                videoItem['fanart'] = item['fanart']

                videoItem['dbid'] = item[dbid]

                Videolist.append(videoItem)
        return Videolist

    def hasVideoExtras(self, target, dbid, file):
        # If the service is on, then we can just check to see if the overlay image exists
        if Settings.isServiceEnabled():
            # Get the path where the file exists
            rootPath = os_path_join(__profile__, target)
            if not dir_exists(rootPath):
                # Directory does not exist yet, so can't have extras
                return False

            # Generate the name of the file that the overlay will be copied to
            targetFile = os_path_join(rootPath, ("%d.png" % dbid))
            if xbmcvfs.exists(targetFile):
                return True

        # Otherwise, need to do the lookup the old fashioned way of looking for the
        # extras files on the file system (This is much slower)
        else:
            videoExtras = VideoExtrasBase(file, target)
            # We are only checking for existence of extras, no need for fanart
            firstExtraFile = videoExtras.findExtras(True)
            if firstExtraFile:
                log("MenuNavigator: Extras found for (%d) %s" % (dbid, file))
                return True

        return False

    # Shows all the extras for a given movie or TV Show
    def showExtras(self, path, target, extrasParentTitle="", extrasDefaultFanArt="", extrasDefaultIconImage=""):
        # Check if the use database setting is enabled
        extrasDb = None
        if Settings.isDatabaseEnabled():
            extrasDb = ExtrasDB()

        # Create the extras class that will be used to process the extras
        videoExtras = VideoExtrasBase(path, target)

        # Perform the search command
        files = videoExtras.findExtras(extrasDb=extrasDb, defaultFanArt=extrasDefaultFanArt)

        tvShowTitle = ""
        if target == MenuNavigator.TVSHOWS:
            tvShowTitle = extrasParentTitle

        if len(files) > 0:
            # Start by adding an option to Play All
            anItem = xbmcgui.ListItem(__addon__.getLocalizedString(32101), path=path)
            # Get the first items fanart for the play all option
            anItem.setProperty("Fanart_Image", files[0].getFanArt())

            if tvShowTitle != "":
                anItem.setInfo('video', {'TvShowTitle': tvShowTitle})

            if extrasParentTitle != "":
                anItem.setInfo('video', {'Title': extrasParentTitle})

            if extrasDefaultIconImage != "":
                anItem.setIconImage(extrasDefaultIconImage)

            anItem.addContextMenuItems([], replaceItems=True)
            url = self._build_url({'mode': 'playallextras', 'foldername': target, 'path': path, 'parentTitle': extrasParentTitle})
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=url, listitem=anItem, isFolder=False)

        # Add each of the extras to the list to display
        for anExtra in files:
            # Create the list item
            li = anExtra.createListItem(parentTitle=extrasParentTitle, tvShowTitle=tvShowTitle, defaultIconImage=extrasDefaultIconImage)
            # Hack, if the "TotalTime" and "ResumeTime" are set on the list item
            # and it is partially watched, then XBMC will display the continue dialog
            # However we can not get what the user selects from this dialog, so it
            # will always continue.  Found out that we can hack this by clearing
            # the "TotalTime" property
            # http://forum.xbmc.org/showthread.php?tid=192627
            li.setProperty("TotalTime", "")

            li.addContextMenuItems([], replaceItems=True)
            li.addContextMenuItems(self._getContextMenu(anExtra, target, path, extrasParentTitle), replaceItems=True)
            url = self._build_url({'mode': 'playextra', 'foldername': target, 'path': path, 'filename': anExtra.getFilename().encode("utf-8"), 'parentTitle': extrasParentTitle})
            xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=url, listitem=li, isFolder=False)

        xbmcplugin.endOfDirectory(self.addon_handle)

    # Play all the extras for a given movie or TV Show
    def playAllExtras(self, path, target, extrasParentTitle):
        # Check if the use database setting is enabled
        extrasDb = None
        if Settings.isDatabaseEnabled():
            extrasDb = ExtrasDB()

        # Create the extras class that will be used to process the extras
        videoExtras = VideoExtrasBase(path, target)

        # Perform the search command
        # No need for fanart default as only getting a list to play, not display
        files = videoExtras.findExtras(extrasDb=extrasDb)

        ExtrasPlayer.playAll(files, extrasParentTitle)

    def playExtra(self, path, target, filename, extrasParentTitle="", forceResume=False, fromStart=False):
        # Check if the use database setting is enabled
        extrasDb = None
        if Settings.isDatabaseEnabled():
            extrasDb = ExtrasDB()

        # Create the extras class that will be used to process the extras
        videoExtras = VideoExtrasBase(path, target)

        # Perform the search command
        # No need for fanart default as only getting a list to play, not display
        files = videoExtras.findExtras(extrasDb=extrasDb)
        for anExtra in files:
            if anExtra.isFilenameMatch(filename):
                log("MenuNavigator: Found  = %s" % filename)

                # Check if we are forcing playback from the start
                if fromStart is not False:
                    anExtra.setResumePoint(0)

                # If part way viewed prompt the user for resume or play from beginning
                if (anExtra.getResumePoint()) > 0 and (forceResume is not True):
                    resumeWindow = VideoExtrasResumeWindow.createVideoExtrasResumeWindow(anExtra.getDisplayResumePoint())
                    resumeWindow.doModal()

                    # Check the return value, if exit, then we play nothing
                    if resumeWindow.isExit():
                        return
                    # If requested to restart from beginning, reset the resume point before playing
                    if resumeWindow.isRestart():
                        anExtra.setResumePoint(0)
                    # Default is to actually resume

                ExtrasPlayer.performPlayAction(anExtra, extrasParentTitle)

    def markAsWatched(self, path, target, filename):
        # If marking as watched we need to set the resume time so it doesn't
        # start in the middle the next time it starts
        if Settings.isDatabaseEnabled():
            # Create the extras class that will be used to process the extras
            videoExtras = VideoExtrasBase(path, target)

            # Perform the search command
            extrasDb = ExtrasDB()
            # We are only updating the DB for an entry already shown, no need for fanart
            files = videoExtras.findExtras(extrasDb=extrasDb)
            for anExtra in files:
                if anExtra.isFilenameMatch(filename):
                    log("MenuNavigator: Found  = %s" % filename)
                    anExtra.setResumePoint(anExtra.getTotalDuration())
                    anExtra.saveState()
                    # Update the display
                    xbmc.executebuiltin("Container.Refresh")

    def markAsUnwatched(self, path, target, filename):
        # If marking as watched we need to set the resume time so it doesn't
        # start in the middle the next time it starts
        if Settings.isDatabaseEnabled():
            # Create the extras class that will be used to process the extras
            videoExtras = VideoExtrasBase(path, target)

            # Perform the search command
            extrasDb = ExtrasDB()
            # We are only updating the DB for an entry already shown, no need for fanart
            files = videoExtras.findExtras(extrasDb=extrasDb)
            for anExtra in files:
                if anExtra.isFilenameMatch(filename):
                    log("MenuNavigator: Found  = %s" % filename)
                    anExtra.setResumePoint(0)
                    anExtra.saveState()
                    # Update the display
                    xbmc.executebuiltin("Container.Refresh")

    def editTitle(self, target, path, filename):
        # Create the extras class that will be used to process the extras
        videoExtras = VideoExtrasBase(path, target)

        # Perform the search command
        # We are only updating the NFO for an entry already shown, no need for fanart
        files = videoExtras.findExtras()
        for anExtra in files:
            if anExtra.isFilenameMatch(filename):
                log("MenuNavigator: Found  = %s" % filename)

                # Prompt the user for the new name
                keyboard = xbmc.Keyboard()
                keyboard.setDefault(anExtra.getDisplayName())
                keyboard.doModal()

                if keyboard.isConfirmed():
                    try:
                        newtitle = keyboard.getText().decode("utf-8")
                    except:
                        newtitle = keyboard.getText()

                    # Only set the title if it has changed
                    if (newtitle != anExtra.getDisplayName()) and (len(newtitle) > 0):
                        isTv = (target == MenuNavigator.TVSHOWS)
                        result = anExtra.setTitle(newtitle, isTV=isTv)
                        if not result:
                            xbmcgui.Dialog().ok(__addon__.getLocalizedString(32102), __addon__.getLocalizedString(32109))
                        else:
                            # Update the display
                            xbmc.executebuiltin("Container.Refresh")

    def editPlot(self, target, path, filename):
        # Create the extras class that will be used to process the extras
        videoExtras = VideoExtrasBase(path, target)

        # Perform the search command
        # We are only updating the NFO for an entry already shown, no need for fanart
        files = videoExtras.findExtras()
        for anExtra in files:
            if anExtra.isFilenameMatch(filename):
                log("MenuNavigator: Found  = %s" % filename)

                # Prompt the user for the new name
                keyboard = xbmc.Keyboard()
                keyboard.setDefault(anExtra.getPlot())
                keyboard.doModal()

                if keyboard.isConfirmed():
                    try:
                        newplot = keyboard.getText().decode("utf-8")
                    except:
                        newplot = keyboard.getText()

                    # Only set the title if it has changed
                    if (newplot != anExtra.getPlot()) and ((len(newplot) > 0) or (anExtra.getPlot() is not None)):
                        isTv = (target == MenuNavigator.TVSHOWS)
                        result = anExtra.setPlot(newplot, isTV=isTv)
                        if not result:
                            xbmcgui.Dialog().ok(__addon__.getLocalizedString(32102), __addon__.getLocalizedString(32115))
                        else:
                            # Update the display
                            xbmc.executebuiltin("Container.Refresh")

    def _getContextMenu(self, extraItem, target, path, extrasParentTitle):
        ctxtMenu = []
        # Resume
        if extraItem.getResumePoint() > 0:
            cmd = self._build_url({'mode': 'resumeextra', 'foldername': target, 'path': path, 'filename': extraItem.getFilename().encode("utf-8"), 'parentTitle': extrasParentTitle})
            ctxtMenu.append(("%s %s" % (__addon__.getLocalizedString(32104), extraItem.getDisplayResumePoint()), 'XBMC.RunPlugin(%s)' % cmd))

        # Play Now
        cmd = self._build_url({'mode': 'beginextra', 'foldername': target, 'path': path, 'filename': extraItem.getFilename().encode("utf-8"), 'parentTitle': extrasParentTitle})
        ctxtMenu.append((__addon__.getLocalizedString(32105), 'XBMC.RunPlugin(%s)' % cmd))

        # Mark As Watched
        if (extraItem.getWatched() == 0) or (extraItem.getResumePoint() > 0):
            cmd = self._build_url({'mode': 'markwatched', 'foldername': target, 'path': path, 'filename': extraItem.getFilename().encode("utf-8")})
            ctxtMenu.append((__addon__.getLocalizedString(32106), 'XBMC.RunPlugin(%s)' % cmd))

        # Mark As Unwatched
        if (extraItem.getWatched() != 0) or (extraItem.getResumePoint() > 0):
            cmd = self._build_url({'mode': 'markunwatched', 'foldername': target, 'path': path, 'filename': extraItem.getFilename().encode("utf-8")})
            ctxtMenu.append((__addon__.getLocalizedString(32107), 'XBMC.RunPlugin(%s)' % cmd))

        # Edit Title
        cmd = self._build_url({'mode': 'edittitle', 'foldername': target, 'path': path, 'filename': extraItem.getFilename().encode("utf-8")})
        ctxtMenu.append((__addon__.getLocalizedString(32108), 'XBMC.RunPlugin(%s)' % cmd))

        # Edit Plot
        cmd = self._build_url({'mode': 'editplot', 'foldername': target, 'path': path, 'filename': extraItem.getFilename().encode("utf-8")})
        ctxtMenu.append((__addon__.getLocalizedString(32114), 'XBMC.RunPlugin(%s)' % cmd))

        return ctxtMenu


################################
# Main of the VideoExtras Plugin
################################
if __name__ == '__main__':
    # Get all the arguments
    base_url = sys.argv[0]
    addon_handle = int(sys.argv[1])
    args = urlparse.parse_qs(sys.argv[2][1:])

    # Record what the plugin deals with, files in our case
    xbmcplugin.setContent(addon_handle, 'files')

    # Get the current mode from the arguments, if none set, then use None
    mode = args.get('mode', None)

    log("VideoExtrasPlugin: Called with addon_handle = %d" % addon_handle)

    # If None, then at the root
    if mode is None:
        log("VideoExtrasPlugin: Mode is NONE - showing root menu")
        menuNav = MenuNavigator(base_url, addon_handle)
        menuNav.showRootMenu()
    elif mode[0] == 'folder':
        log("VideoExtrasPlugin: Mode is FOLDER")

        # Get the actual folder that was navigated to
        foldername = args.get('foldername', None)

        if (foldername is not None) and (len(foldername) > 0):
            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.showFolder(foldername[0])

    elif mode[0] == 'listextras':
        log("VideoExtrasPlugin: Mode is LIST EXTRAS")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        foldername = args.get('foldername', None)
        parentTitle = args.get('parentTitle', None)
        defaultFanArt = args.get('defaultFanArt', None)
        defaultIconImage = args.get('defaultIconImage', None)

        if (path is not None) and (len(path) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to load extras for %s" % path[0])
            extrasParentTitle = ""
            if (parentTitle is not None) and (len(parentTitle) > 0):
                extrasParentTitle = parentTitle[0]
            extrasDefaultFanArt = ""
            if (defaultFanArt is not None) and (len(defaultFanArt) > 0):
                extrasDefaultFanArt = defaultFanArt[0]
            extrasDefaultIconImage = ""
            if (defaultIconImage is not None) and (len(defaultIconImage) > 0):
                extrasDefaultIconImage = defaultIconImage[0]

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.showExtras(path[0], foldername[0], extrasParentTitle, extrasDefaultFanArt, extrasDefaultIconImage)

    elif mode[0] == 'playallextras':
        log("VideoExtrasPlugin: Mode is PLAY ALL EXTRAS")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        foldername = args.get('foldername', None)
        parentTitle = args.get('parentTitle', None)

        if (path is not None) and (len(path) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play all extras for %s" % path[0])
            extrasParentTitle = ""
            if (parentTitle is not None) and (len(parentTitle) > 0):
                extrasParentTitle = parentTitle[0]

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.playAllExtras(path[0], foldername[0], extrasParentTitle)

    elif mode[0] == 'playextra':
        log("VideoExtrasPlugin: Mode is PLAY EXTRA")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        foldername = args.get('foldername', None)
        filename = args.get('filename', None)
        parentTitle = args.get('parentTitle', None)

        if (path is not None) and (len(path) > 0) and (filename is not None) and (len(filename) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play extras for %s" % path[0])
            log("VideoExtrasPlugin: Extras file to play %s" % filename[0])
            extrasParentTitle = ""
            if (parentTitle is not None) and (len(parentTitle) > 0):
                extrasParentTitle = parentTitle[0]

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.playExtra(path[0], foldername[0], filename[0], extrasParentTitle)

    elif mode[0] == 'resumeextra':
        log("VideoExtrasPlugin: Mode is RESUME EXTRA")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        foldername = args.get('foldername', None)
        filename = args.get('filename', None)
        parentTitle = args.get('parentTitle', None)

        if (path is not None) and (len(path) > 0) and (filename is not None) and (len(filename) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play extras for %s" % path[0])
            log("VideoExtrasPlugin: Extras file to play %s" % filename[0])
            extrasParentTitle = ""
            if (parentTitle is not None) and (len(parentTitle) > 0):
                extrasParentTitle = parentTitle[0]

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.playExtra(path[0], foldername[0], filename[0], extrasParentTitle, forceResume=True)

    elif mode[0] == 'beginextra':
        log("VideoExtrasPlugin: Mode is BEGIN EXTRA")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        foldername = args.get('foldername', None)
        filename = args.get('filename', None)
        parentTitle = args.get('parentTitle', None)

        if (path is not None) and (len(path) > 0) and (filename is not None) and (len(filename) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play extras for %s" % path[0])
            log("VideoExtrasPlugin: Extras file to play %s" % filename[0])
            extrasParentTitle = ""
            if (parentTitle is not None) and (len(parentTitle) > 0):
                extrasParentTitle = parentTitle[0]

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.playExtra(path[0], foldername[0], filename[0], extrasParentTitle, fromStart=True)

    elif mode[0] == 'markwatched':
        log("VideoExtrasPlugin: Mode is MARK WATCHED")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        foldername = args.get('foldername', None)
        filename = args.get('filename', None)

        if (path is not None) and (len(path) > 0) and (filename is not None) and (len(filename) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play extras for %s" % path[0])
            log("VideoExtrasPlugin: Extras file to play %s" % filename[0])

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.markAsWatched(path[0], foldername[0], filename[0])

    elif mode[0] == 'markunwatched':
        log("VideoExtrasPlugin: Mode is MARK UNWATCHED")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        foldername = args.get('foldername', None)
        filename = args.get('filename', None)

        if (path is not None) and (len(path) > 0) and (filename is not None) and (len(filename) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play extras for %s" % path[0])
            log("VideoExtrasPlugin: Extras file to play %s" % filename[0])

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.markAsUnwatched(path[0], foldername[0], filename[0])

    elif mode[0] == 'edittitle':
        log("VideoExtrasPlugin: Mode is EDIT TITLE")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        filename = args.get('filename', None)
        foldername = args.get('foldername', None)

        if (path is not None) and (len(path) > 0) and (filename is not None) and (len(filename) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play extras for %s" % path[0])
            log("VideoExtrasPlugin: Extras file to play %s" % filename[0])

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.editTitle(foldername[0], path[0], filename[0])

    elif mode[0] == 'editplot':
        log("VideoExtrasPlugin: Mode is EDIT PLOT")

        # Get the actual path that was navigated to
        path = args.get('path', None)
        filename = args.get('filename', None)
        foldername = args.get('foldername', None)

        if (path is not None) and (len(path) > 0) and (filename is not None) and (len(filename) > 0) and (foldername is not None) and (len(foldername) > 0):
            log("VideoExtrasPlugin: Path to play extras for %s" % path[0])
            log("VideoExtrasPlugin: Extras file to play %s" % filename[0])

            menuNav = MenuNavigator(base_url, addon_handle)
            menuNav.editPlot(foldername[0], path[0], filename[0])