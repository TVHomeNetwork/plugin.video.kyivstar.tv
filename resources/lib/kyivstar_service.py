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
from resources.lib.kyivstar_http_server import KyivstarHttpServer
from resources.lib.channel_manager import ChannelManager

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
        self.live_stream_server_port = service.addon.getSetting('live_stream_server_port')
        self.live_inputstream = service.addon.getSetting('live_stream_inputstream')
        self.m3u_include_kyivstar_groups = service.addon.getSetting('m3u_include_kyivstar_groups')
        self.m3u_include_favorites_group = service.addon.getSetting('m3u_include_favorites_group')

    def onSettingsChanged(self):
        service = self.service
        session_id = service.addon.getSetting('session_id')

        m3u_start_saving = False
        path_m3u = service.addon.getSetting('path_m3u')
        name_m3u = service.addon.getSetting('name_m3u')
        if path_m3u != self.path_m3u or name_m3u != self.name_m3u:
            if path_m3u != '' and name_m3u != '':
                self.service.m3u_file_path = path_m3u + name_m3u
            else:
                self.service.m3u_file_path = None
            if self.service.m3u_file_path and not xbmcvfs.exists(self.service.m3u_file_path):
                m3u_start_saving = True
            self.path_m3u = path_m3u
            self.name_m3u = name_m3u

        cancel_epg_saving = None
        path_epg = service.addon.getSetting('path_epg')
        name_epg = service.addon.getSetting('name_epg')
        if path_epg != self.path_epg or name_epg != self.name_epg:
            if service.save_epg_index >= 0:
                loc_str_1 = service.addon.getLocalizedString(30114) # 'Warning'
                loc_str_2 = service.addon.getLocalizedString(30115) # 'This will cancel the EPG save process that is not yet complete. Continue?'
                loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
                loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
                cancel_epg_saving = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
            if cancel_epg_saving == False:
                service.addon.setSetting('path_epg', self.path_epg)
                service.addon.setSetting('name_epg', self.name_epg)
                return
            if path_epg != '' and name_epg != '':
                self.service.epg_file_path = path_epg + name_epg
            else:
                self.service.epg_file_path = None
            if self.service.epg_file_path and not xbmcvfs.exists(self.service.epg_file_path):
                service.epg_start_saving = True
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
            if service.save_epg_index >= 0 and cancel_epg_saving == None:
                loc_str_1 = service.addon.getLocalizedString(30114) # 'Warning'
                loc_str_2 = service.addon.getLocalizedString(30115) # 'This will cancel the EPG save process that is not yet complete. Continue?'
                loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
                loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
                cancel_epg_saving = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
            if cancel_epg_saving == False:
                service.addon.setSetting('locale', self.locale)
                return
            # are we need send request?
            if service.get_session_status() != KyivstarService.SESSION_EMPTY:
                service.request.change_locale(session_id, locale)
            service.request.headers['x-vidmind-locale'] = locale
            self.locale = locale
            if self.service.m3u_file_path:
                m3u_start_saving = True
            if self.service.epg_file_path:
                service.epg_start_saving = True

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

        m3u_include_kyivstar_groups = service.addon.getSetting('m3u_include_kyivstar_groups')
        if m3u_include_kyivstar_groups != self.m3u_include_kyivstar_groups:
            if self.service.m3u_file_path:
                m3u_start_saving = True
            self.m3u_include_kyivstar_groups = m3u_include_kyivstar_groups

        m3u_include_favorites_group = service.addon.getSetting('m3u_include_favorites_group')
        if m3u_include_favorites_group != self.m3u_include_favorites_group:
            if self.service.m3u_file_path:
                m3u_start_saving = True
            self.m3u_include_favorites_group = m3u_include_favorites_group

        if m3u_start_saving:
            service.save_m3u()

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

        self.m3u_file_path = None
        path_m3u = self.addon.getSetting('path_m3u')
        name_m3u = self.addon.getSetting('name_m3u')
        if path_m3u != '' and name_m3u != '':
            self.m3u_file_path = path_m3u + name_m3u

        self.epg_file_path = None
        path_epg = self.addon.getSetting('path_epg')
        name_epg = self.addon.getSetting('name_epg')
        if path_epg != '' and name_epg != '':
            self.epg_file_path = path_epg + name_epg

        self.epg_start_saving = False

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

        if not self.m3u_file_path:
            loc_str = self.addon.getLocalizedString(30206) # 'To save M3U list you must set path and name of file in settings.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        xbmc.log("KyivstarService: Saving M3U started.", xbmc.LOGDEBUG)
        channel_manager = ChannelManager()

        if not channel_manager.download(self):
            loc_str = self.addon.getLocalizedString(30207) # 'Error during list saving. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            self.set_session_status(KyivstarService.SESSION_INACTIVE)
            return

        # If we write data stright to the 'self.m3u_file_path' file, pvr.iptvsimple can stuck on updating channels.
        temp = xbmcvfs.translatePath('special://temp') + 'test.m3u'

        channel_manager.save(temp)

        xbmcvfs.copy(temp, self.m3u_file_path)
        xbmcvfs.delete(temp)

        if self.addon.getSetting('iptv_sc_reload_when_m3u_saved') == 'true':
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
            time.sleep(1)
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')

        loc_str = self.addon.getLocalizedString(30208) # 'Save M3U completed.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
        xbmc.log("KyivstarService: Saving M3U completed.", xbmc.LOGDEBUG)

    def save_epg(self):
        if self.get_session_status() == KyivstarService.SESSION_EMPTY:
            loc_str = self.addon.getLocalizedString(30204) # 'Log in to the plugin'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        if not self.m3u_file_path:
            loc_str = self.addon.getLocalizedString(30209) # 'M3U list does not exists.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        if not xbmcvfs.exists(self.m3u_file_path):
            loc_str = self.addon.getLocalizedString(30209) # 'M3U list does not exists.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        if not self.epg_file_path:
            loc_str = self.addon.getLocalizedString(30210) # 'To save EPG you must set path and name of file in settings.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return

        xbmc.log("KyivstarService: Saving EPG started.", xbmc.LOGDEBUG)
        xml_root = etree.Element("tv")

        channel_manager = ChannelManager()
        channel_manager.load(self.m3u_file_path)

        assets = []

        for channel in channel_manager.enabled:
            xml_channel = etree.SubElement(xml_root, "channel", attrib={"id": channel.id})
            etree.SubElement(xml_channel, "display-name").text = channel.name
            etree.SubElement(xml_channel, "icon", src=channel.logo)

            #only VIRTUAL channels must have catchup-id in epg
            catchup_avaliable = channel.catchup and channel.virtual

            assets.append({
                'id': channel.id,
                'catchup':catchup_avaliable
            })

        self.save_epg_xml_root = xml_root
        self.save_epg_assets = assets
        self.save_epg_index = 0
        self.save_epg_file_path = self.epg_file_path
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

        f = xbmcvfs.File(self.save_epg_file_path, 'w')
        f.write(epg_list)
        f.close()

        self.save_epg_index = -1
        del self.save_epg_xml_root
        del self.save_epg_assets

        if self.addon.getSetting('iptv_sc_reload_when_epg_saved') == 'true':
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
            time.sleep(1)
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')

        loc_str = self.addon.getLocalizedString(30211) # 'Save EPG completed.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
        xbmc.log("KyivstarService: Saving EPG completed.", xbmc.LOGDEBUG)

    def run(self):
        monitor = KyivstarServiceMonitor(self)
        self.channel_manager = ChannelManager()

        check_session_timer = 0
        self.check_session_status()

        if self.get_session_status() == KyivstarService.SESSION_INACTIVE:
            loc_str = self.addon.getLocalizedString(30212) # 'Error during session status check. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            check_session_timer = int(time.time())

        if self.get_session_status() != KyivstarService.SESSION_EMPTY:
            if self.m3u_file_path and not xbmcvfs.exists(self.m3u_file_path):
                self.save_m3u()
            if self.epg_file_path and not xbmcvfs.exists(self.epg_file_path):
                self.epg_start_saving = True

        self.live_stream_server = KyivstarHttpServer(self)
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
                    if self.epg_file_path and current_time.tm_hour >= refresh_hour and current_time.tm_mday != refresh_day:
                        if not xbmcvfs.exists(self.epg_file_path):
                            xbmc.log("KyivstarService: refresh_epg creating new file", xbmc.LOGINFO)
                            self.epg_start_saving = True
                        else:
                            st = xbmcvfs.Stat(self.epg_file_path)
                            self.refreshed = time.localtime(st.st_mtime())
                            if current_time.tm_mday != self.refreshed.tm_mday:
                                xbmc.log("KyivstarService: refresh_epg updating old file", xbmc.LOGINFO)
                                self.epg_start_saving = True

                if self.epg_start_saving:
                    self.epg_start_saving = False
                    if self.save_epg_index >= 0:
                        self.save_epg_index = -1
                        del self.save_epg_xml_root
                        del self.save_epg_assets
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
