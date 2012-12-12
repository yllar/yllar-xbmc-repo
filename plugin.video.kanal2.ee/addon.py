# -*- coding:utf-8-*-
#
#      Copyright (C) 2012 Yllar Pajus
#      http://loru.mine.nu
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this Program; see the file LICENSE.txt.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#
from xml.etree import ElementTree
import os
import sys
import urlparse
import urllib2
import re

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

import buggalo

class Kanal2Exception(Exception):
    pass

class Kanal2Addon(object):
  def downloadUrl(self,url):
    for retries in range(0, 5):
      try:
        r = urllib2.Request(url.encode('iso-8859-1', 'replace'))
        r.add_header('User-Agent', 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:10.0.2) Gecko/20100101 Firefox/10.0.2')
        u = urllib2.urlopen(r, timeout = 30)
        contents = u.read()
        u.close()
        return contents
      except Exception, ex:
        if retries > 5:
          raise Kanal2Exception(ex)

  # list all the shows
  def listPrograms(self):
    url = "http://kanal2.ee/vaatasaateid"
    buggalo.addExtraData('url', url)
    html = self.downloadUrl(url)
    
    saated = {}
    for m in re.finditer('href="vaatasaateid/([^"]+)">([^<]+)</a>', html):
      if "=" not in m.group(1): #only add if show doesn't have any parameter (duplicate)
        saated[m.group(1)] = m.group(2)
    for m in re.finditer('vaatasaateid%2F([^\']+)\'\);">([^<]+)</a>', html):
      saated[m.group(1)] = m.group(2)
    for m in re.finditer('vaatasaateid%2F([^\']+)\'\);return false;">([^<]+)</a>', html):
      saated[m.group(1)] = m.group(2)
      
    items = list()
    for key,value in sorted(saated.iteritems()):
      fanart = self.downloadAndCacheFanart(key, None) # set fetch to None so it would not fetch all the pictures at once
      item = xbmcgui.ListItem(value, iconImage=fanart) 
      item.setProperty('Fanart_Image', fanart)
      items.append((PATH + '?program=%s' % key, item, True))
    xbmcplugin.addDirectoryItems(HANDLE, items)
    xbmcplugin.endOfDirectory(HANDLE)

  # return Telecast ID of the show 
  def getTelecastID(self,telecastID):
    url = "http://kanal2.ee/saated/"
    buggalo.addExtraData('url', url)
    html = self.downloadUrl(url + telecastID)
    for s in re.finditer('xml:.*=([^"]+)",',html):
      return  s.group(1)

  # list all episodes
  def listVideos(self,saade):
    telecast = 'http://kanal2.ee/video/showreelapi?telecastid=%s' % self.getTelecastID(saade)
    fanart = self.downloadAndCacheFanart(saade, True) # download pictures
    buggalo.addExtraData('url', telecast)
    telecastxml = self.downloadUrl(telecast)
    if not telecastxml:
      raise Kanal2Exception(ADDON.getLocalizedString(203))

    doc = ElementTree.fromstring(telecastxml.replace('&', '&amp;'))
    items = list()
    group = doc.findall("items/video")
    for node in group:
      title = node.findtext('name')
      #rating = int(node.findtext('rating/value')) * 2.0
      rating = int(3.4563) * 2.0
      date = re.search('\(([^\)]+)\)',title, re.DOTALL )
      if date:
        date = date.group(1)
      else:
        date = '01.01.2012'
      infoLabels = {
        'rating' : rating,
        'date' : date,
        'title' : title
      }
      #print "Pilt: " + node.findtext('thumbUrl')
      url = node.findtext('clickUrl')
      if url: #get IDs 
        if "javascript" in url:
          idsplit = re.search('.*%3D([^\']+)\'',url, re.DOTALL)
        else:
          idsplit = re.search('.*=([^$]+)',url, re.DOTALL)
        #print "ID: http://kanal2.ee/video/playerPlaylistApi?id=%s" %  idsplit.group(1)
        item = xbmcgui.ListItem(title, iconImage = fanart)
        item.setInfo('video', infoLabels)
        item.setProperty('IsPlayable', 'true')
        item.setProperty('Fanart_Image', fanart)
        items.append((PATH + '?show=%s' %  idsplit.group(1), item))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_DATE)
    xbmcplugin.addDirectoryItems(HANDLE, items)
    xbmcplugin.endOfDirectory(HANDLE)

  # get actual video file and start playing
  def getVideoUrl(self,videoid):
    url = 'http://kanal2.ee/video/playerPlaylistApi?id=%s' %  videoid
    buggalo.addExtraData('url', url)
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()

    videoxml = self.downloadUrl(url)
    if not videoxml:
      raise Kanal2Exception(ADDON.getLocalizedString(203))

    dl = ElementTree.fromstring(videoxml)
    for video in dl.findall("playlist/video"):
      item = xbmcgui.ListItem(video.findtext('name'), iconImage = ICON, path = video.findtext('videoUrl'))
      videoUrl = video.findtext('videoUrl')
      if not videoUrl:
	raise Kanal2Exception(ADDON.getLocalizedString(202))
      playlist.add(videoUrl,item)
      firstItem = item
    #start = 0
    xbmcplugin.setResolvedUrl(HANDLE, True, item)

  def downloadAndCacheFanart(self, saade,fetch):
    url = 'http://kanal2.ee/saated/%s' % saade
    fanartPath = os.path.join(CACHE_PATH, '%s.jpg' % saade.encode('iso-8859-1', 'replace'))
    fanartUrl = None

    if fetch is None:
      html = None
    else:
      html = self.downloadUrl(url)
      
    if not os.path.exists(fanartPath) and html:
      m = re.search('image saated" style="background-image: url\(([^)+]+)',html)
      if m:
	fanartUrl = "http://kanal2.ee/" + m.group(1)

      if fanartUrl:
        imageData = self.downloadUrl(fanartUrl.replace(' ', '%20'))
        if imageData:
          f = open(fanartPath, 'wb')
          f.write(imageData)
          f.close()
          
          return fanartPath
          
    elif os.path.exists(fanartPath):
      return fanartPath
        
    return FANART

  def displayError(self, message = 'n/a'):
    heading = buggalo.getRandomHeading()
    line1 = ADDON.getLocalizedString(200)
    line2 = ADDON.getLocalizedString(201)
    xbmcgui.Dialog().ok(heading, line1, line2, message)

if __name__ == '__main__':
  ADDON = xbmcaddon.Addon()
  PATH = sys.argv[0]
  HANDLE = int(sys.argv[1])
  PARAMS = urlparse.parse_qs(sys.argv[2][1:])

  ICON = os.path.join(ADDON.getAddonInfo('path'), 'icon.png')
  FANART = os.path.join(ADDON.getAddonInfo('path'), 'fanart.jpg')

  CACHE_PATH = xbmc.translatePath(ADDON.getAddonInfo("Profile"))
  if not os.path.exists(CACHE_PATH):
    os.makedirs(CACHE_PATH)

  buggalo.SUBMIT_URL = 'http://loru.mine.nu/exception/submit.php'
  kanal2Addon = Kanal2Addon()
  try:
    if PARAMS.has_key('program'):
      kanal2Addon.listVideos(PARAMS['program'][0])
    elif PARAMS.has_key('show'):
      kanal2Addon.getVideoUrl(PARAMS['show'][0])
    else:
      kanal2Addon.listPrograms()
  except Kanal2Exception, ex:
    kanal2Addon.displayError(str(ex))
  except Exception:
    buggalo.onExceptionRaised()
