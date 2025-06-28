import sys
import random
import re
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import xml.etree.ElementTree as etree

from resources.lib.kyivstar_request import KyivstarRequest
from resources.lib.live_stream_server import LiveStreamServer

class KyivstarServiceMonitor(xbmc.Monitor):
    def __init__(self, service):
        xbmc.Monitor.__init__(self)
        self.service = service
        self.path_m3u = service.addon.getSetting('path_m3u')
        self.name_m3u = service.addon.getSetting('name_m3u')
        self.path_epg = service.addon.getSetting('path_epg')
        self.name_epg = service.addon.getSetting('name_epg')
        self.inputstream = service.addon.getSetting('stream_inputstream')
        self.locale = service.addon.getSetting('locale')
        self.live_stream_server_enabled = service.addon.getSetting('live_stream_server_enabled')
        self.live_stream_server_port = service.addon.getSetting('live_stream_server_port')
        self.live_inputstream = service.addon.getSetting('live_stream_inputstream')

    def onSettingsChanged(self):
        service = self.service
        session_id = service.addon.getSetting('session_id')

        path_m3u = service.addon.getSetting('path_m3u')
        name_m3u = service.addon.getSetting('name_m3u')
        if path_m3u != self.path_m3u or name_m3u != self.name_m3u:
            if not xbmcvfs.exists(path_m3u + name_m3u):
                service.save_m3u()
            self.path_m3u = path_m3u
            self.name_m3u = name_m3u

        path_epg = service.addon.getSetting('path_epg')
        name_epg = service.addon.getSetting('name_epg')
        if path_epg != self.path_epg or name_epg != self.name_epg:
            if service.save_epg_index >= 0:
                loc_str = service.addon.getLocalizedString(30205) # 'Can not set new filename and path for epg file while previous saving process is not done.'
                xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
                service.addon.setSetting('path_epg', self.path_epg)
                service.addon.setSetting('name_epg', self.name_epg)
                return
            elif not xbmcvfs.exists(path_epg + name_epg):
                service.save_epg()
            self.path_epg = path_epg
            self.name_epg = name_epg

        inputstream = service.addon.getSetting('stream_inputstream')
        if inputstream != self.inputstream:
            if inputstream != 'default' and xbmc.getCondVisibility('System.HasAddon(%s)' % inputstream) == 0:
                loc_str = service.addon.getLocalizedString(30213) # 'Inputstream addon does not found. Set value to default.'
                xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
                service.addon.setSetting('stream_inputstream', 'default')
                self.inputstream = 'default'
            else:
                self.inputstream = inputstream

        locale = service.addon.getSetting('locale')
        if locale != self.locale:
            # are we need send request?
            if service.get_session_status() != KyivstarService.SESSION_EMPTY:
                service.request.change_locale(session_id, locale)
            service.request.headers['x-vidmind-locale'] = locale
            self.locale = locale

        live_stream_server_enabled = service.addon.getSetting('live_stream_server_enabled')
        if live_stream_server_enabled != self.live_stream_server_enabled:
            if live_stream_server_enabled == 'true':
                service.live_stream_server.start()
            else:
                service.live_stream_server.stop()
            self.live_stream_server_enabled = live_stream_server_enabled

        live_stream_server_port = service.addon.getSetting('live_stream_server_port')
        if live_stream_server_port != self.live_stream_server_port:
            if service.live_stream_server.httpd.server_address[1] != int(live_stream_server_port):
                service.live_stream_server.stop()
                service.live_stream_server.start()
            self.live_stream_server_port = live_stream_server_port

        live_inputstream = service.addon.getSetting('live_stream_inputstream')
        if live_inputstream != self.live_inputstream:
            if inputstream != 'default' and xbmc.getCondVisibility('System.HasAddon(%s)' % inputstream) == 0:
                loc_str = service.addon.getLocalizedString(30213) # 'Inputstream addon does not found. Set value to default.'
                xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
                service.addon.setSetting('live_stream_inputstream', 'default')
                self.live_inputstream = 'default'
            else:
                self.live_inputstream = live_inputstream

class KyivstarService:
    SESSION_EMPTY = "0"
    SESSION_ACTIVE = "1"
    SESSION_INACTIVE = "2"

    def __init__(self):
        self.addon = xbmcaddon.Addon()

        device_id = self.addon.getSetting('device_id')
        if device_id == '':
            device_id = '10000000-1000-4000-8000-100000000000'
            def num_rep(match):
                return random.choice('0123456789abcdef')
            device_id = re.sub(r'[018]', num_rep, device_id)
            self.addon.setSetting('device_id', device_id)

        locale = self.addon.getSetting('locale')

        self.request = KyivstarRequest(device_id, locale)
        self.save_epg_index = -1
        self.refreshed = None

    def set_session_status(self, status):
        window = xbmcgui.Window(10000)
        window.setProperty("KyivstarService_session_status", status)

    def get_session_status(self):
        window = xbmcgui.Window(10000)
        return window.getProperty("KyivstarService_session_status")

    def check_session_status(self):
        session_id = self.addon.getSetting('session_id')
        user_if = self.addon.getSetting('user_id')
        if session_id == '':
            self.set_session_status(KyivstarService.SESSION_EMPTY)
        elif user_if == 'anonymous':
            profile = self.request.login_anonymous()
            if 'userId' not in profile or 'sessionId' not in profile:
                self.set_session_status(KyivstarService.SESSION_INACTIVE)
                return
            self.addon.setSetting('session_id', profile['sessionId'])
            self.set_session_status(KyivstarService.SESSION_ACTIVE)
        elif len(self.request.get_profiles(session_id)) > 0:
            self.set_session_status(KyivstarService.SESSION_ACTIVE)
        else:
            self.set_session_status(KyivstarService.SESSION_INACTIVE)

    def save_m3u(self):
        if self.get_session_status() == KyivstarService.SESSION_EMPTY:
            loc_str = self.addon.getLocalizedString(30204) # 'Log in to the plugin'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        path_m3u = self.addon.getSetting('path_m3u')
        name_m3u = self.addon.getSetting('name_m3u')

        if path_m3u == '' or name_m3u == '':
            loc_str = self.addon.getLocalizedString(30206) # 'To save M3U list you must set path and name of file in settings.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        session_id = self.addon.getSetting('session_id')

        groups = self.request.get_live_channels_groups(session_id)

        if len(groups) == 0:
            loc_str = self.addon.getLocalizedString(30207) # 'Error during list saving. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            self.set_session_status(KyivstarService.SESSION_INACTIVE)
            return

        all_channels_group_id = groups[0].get('assetId', None)
        all_channels = self.request.get_group_elems(session_id, all_channels_group_id)

        if len(all_channels) == 0:
            loc_str = self.addon.getLocalizedString(30207) # 'Error during list saving. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            self.set_session_status(KyivstarService.SESSION_INACTIVE)
            return

        data = '#EXTM3U\n'
        for channel in all_channels:
            if not channel.get('purchased', None):
                continue

            channel_logo = ''
            images = channel.get('images', None)
            if images and len(images) > 0:
                channel_logo = images[0].get('url', None)

            channel_name = channel.get('displayName', None)
            if not channel_name:
                channel_name = channel.get('name', None)

            channel_asset_id = channel.get('assetId', None)

            channel_type = 'IP'
            ctype = channel.get('type', None)
            if ctype:
                channel_type = ctype.get('value', None)

            channel_catchup = ''
            if channel.get('catchupEnabled', None):
                if channel_type == 'IP':
                    channel_catchup = 'catchup="default" catchup-source="plugin://plugin.video.kyivstar.tv/play/%s-%s|{utc}"' % (channel_asset_id, channel_type)
                else:
                    channel_catchup = 'catchup="vod" catchup-source="plugin://plugin.video.kyivstar.tv/play/%s-%s|{catchup-id}"' % (channel_asset_id, channel_type)

            data += '#EXTINF:0 tvg-id="%s" tvg-name="%s" tvg-logo="%s" %s,%s\n' % (channel_asset_id, channel_name, channel_logo, channel_catchup, channel_name)
            data += 'plugin://plugin.video.kyivstar.tv/play/%s-%s|null\n' % (channel_asset_id, channel_type)

        f = xbmcvfs.File(path_m3u + name_m3u, 'w')
        f.write(data.encode("utf-8"))
        f.close()

        loc_str = self.addon.getLocalizedString(30208) # 'Save M3U completed.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)

    def save_epg(self):
        if self.get_session_status() == KyivstarService.SESSION_EMPTY:
            loc_str = self.addon.getLocalizedString(30204) # 'Log in to the plugin'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        path_m3u = self.addon.getSetting('path_m3u')
        name_m3u = self.addon.getSetting('name_m3u')

        if not xbmcvfs.exists(path_m3u + name_m3u):
            loc_str = self.addon.getLocalizedString(30209) # 'M3U list does not exists.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        path_epg = self.addon.getSetting('path_epg')
        name_epg = self.addon.getSetting('name_epg')

        if path_epg == '' or name_epg == '':
            loc_str = self.addon.getLocalizedString(30210) # 'To save EPG you must set path and name of file in settings.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        xml_root = etree.Element("tv")

        f = xbmcvfs.File(path_m3u + name_m3u)
        m3u_list = f.read().split('\n')
        f.close()

        assets = []

        for line in m3u_list:
            if not line.startswith('#EXTINF'):
                continue
            match = re.search('tvg-id=".*?"', line)
            if not match:
                continue
            asset_id = match.group().replace('tvg-id=', '').replace('"','')
            xml_channel = etree.SubElement(xml_root, "channel", attrib={"id": asset_id})
            match = re.search('tvg-name=".*?"', line)
            if match:
                name = match.group().replace('tvg-name=', '').replace('"','')
                etree.SubElement(xml_channel, "display-name").text = name
            match = re.search('tvg-logo=".*?"', line)
            if match:
                logo = match.group().replace('tvg-logo=', '').replace('"','')
                etree.SubElement(xml_channel, "icon", src=logo)

            catchup_avaliable = False
            match = re.search('catchup=".*?"', line)
            #only VIRTUAL channels must have catchup-id in epg
            if match and 'VIRTUAL' in line:
                catchup_avaliable = True

            assets.append({
                'id': asset_id,
                'catchup':catchup_avaliable
            })

        self.save_epg_xml_root = xml_root
        self.save_epg_assets = assets
        self.save_epg_index = 0
        self.save_epg_include_desc = self.addon.getSetting('epg_include_description') == 'true'
        self.step_save_epg()

    def strip_html(self, text):
        return re.sub('<[^>]*?>', '', text)

    def step_save_epg(self):
        session_id = self.addon.getSetting('session_id')

        i = self.save_epg_index
        end_step = i + int(self.addon.getSetting('epg_group_requests_count'))
        assets = self.save_epg_assets
        length_assets = len(assets)
        if end_step > length_assets:
            end_step = length_assets
        xml_root = self.save_epg_xml_root

        while i < end_step:
            asset_id = assets[i]['id']
            catchup_avaliable = assets[i]['catchup']
            epg_data = self.request.get_elem_epg_data(session_id, asset_id)

            if len(epg_data) == 0:
                xbmc.log("KyivstarService step_save_epg: asset %s does not have epg data. " % (asset_id), xbmc.LOGINFO)
                i += 1
                continue

            for epg_day_data in epg_data:
                if 'programList' not in epg_day_data:
                    continue

                if len(epg_day_data['programList']) == 0:
                    continue

                for program in epg_day_data['programList']:
                    program_attrib = {
                        "start": time.strftime('%Y%m%d%H%M%S', time.gmtime(program['start']/1000)) + " +0000",
                        "stop": time.strftime('%Y%m%d%H%M%S', time.gmtime(program['finish']/1000)) + " +0000",
                        "channel": asset_id
                    }
                    if catchup_avaliable:
                        program_attrib.update({
                            'catchup-id':str(int(program['start']/1000))
                        })
                    xml_program = etree.SubElement(xml_root, "programme", attrib=program_attrib)
                    etree.SubElement(xml_program, "title").text = program['title']
                    if self.save_epg_include_desc:
                        etree.SubElement(xml_program, "desc").text = self.strip_html(program['desc'])
            i += 1
        self.save_epg_index = i

        if i < length_assets:
            return

        tree = etree.ElementTree(xml_root)
        etree.indent(tree, space="  ", level=0)

        epg_list = '<?xml version="1.0" encoding="utf-8"?>\n'.encode("utf-8") + etree.tostring(xml_root, encoding='utf-8')

        path_epg = self.addon.getSetting('path_epg')
        name_epg = self.addon.getSetting('name_epg')

        f = xbmcvfs.File(path_epg + name_epg, 'w')
        f.write(epg_list)
        f.close()

        self.save_epg_index = -1
        del self.save_epg_xml_root
        del self.save_epg_assets

        loc_str = self.addon.getLocalizedString(30211) # 'Save EPG completed.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)

    def run(self):
        monitor = KyivstarServiceMonitor(self)

        check_session_timer = 0
        self.check_session_status()

        if self.get_session_status() == KyivstarService.SESSION_INACTIVE:
            loc_str = self.addon.getLocalizedString(30212) # 'Error during session status check. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            check_session_timer = int(time.time())

        if self.get_session_status() != KyivstarService.SESSION_EMPTY:
            path_m3u = self.addon.getSetting('path_m3u')
            name_m3u = self.addon.getSetting('name_m3u')
            if path_m3u != '' and name_m3u != '' and not xbmcvfs.exists(path_m3u + name_m3u):
                self.save_m3u()
            path_epg = self.addon.getSetting('path_epg')
            name_epg = self.addon.getSetting('name_epg')
            if path_epg != '' and name_epg != '' and not xbmcvfs.exists(path_epg + name_epg):
                self.save_epg()

        self.live_stream_server = LiveStreamServer(self)
        if self.addon.getSetting('live_stream_server_enabled') == 'true':
            self.live_stream_server.start()

        while not monitor.abortRequested():
            try:
                if self.save_epg_index >= 0:
                    self.step_save_epg()
                    if self.save_epg_index < 0:
                        self.refreshed = time.localtime()

                if self.get_session_status() == KyivstarService.SESSION_INACTIVE:
                    if int(time.time()) - check_session_timer > 5 * 60:
                        if check_session_timer != 0:
                            self.check_session_status()
                        check_session_timer = int(time.time())

                if self.save_epg_index < 0:
                    current_time = time.localtime()
                    refresh_day = 0
                    if self.refreshed:
                        refresh_day = self.refreshed.tm_mday
                    refresh_hour = self.addon.getSettingInt('epg_refresh_hour')
                    if current_time.tm_hour >= refresh_hour and current_time.tm_mday != refresh_day:
                        path_epg = self.addon.getSetting('path_epg')
                        name_epg = self.addon.getSetting('name_epg')
                        if path_epg != '' and name_epg != '':
                            if not xbmcvfs.exists(path_epg + name_epg):
                                xbmc.log("KyivstarService: refresh_epg creating new file", xbmc.LOGINFO)
                                self.save_epg()
                            else:
                                st = xbmcvfs.Stat(path_epg + name_epg)
                                self.refreshed = time.localtime(st.st_mtime())
                                if current_time.tm_mday != self.refreshed.tm_mday:
                                    xbmc.log("KyivstarService: refresh_epg updating old file", xbmc.LOGINFO)
                                    self.save_epg()

                wait_time = 60
                if self.save_epg_index >= 0:
                    wait_time = self.addon.getSettingInt('epg_group_requests_delay')
                if monitor.waitForAbort(wait_time):
                    break

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                xbmc.log("KyivstarService exception (line %s): %s" % (exc_tb.tb_lineno,str(e)), xbmc.LOGERROR)

        self.live_stream_server.stop()
