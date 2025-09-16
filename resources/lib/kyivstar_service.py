import traceback
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
from resources.lib.archive_manager import ArchiveManager
from resources.lib.save_manager import SaveManager
from resources.lib.common import strip_html, SessionStatus

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

        path_m3u = service.addon.getSetting('path_m3u')
        name_m3u = service.addon.getSetting('name_m3u')
        if path_m3u != self.path_m3u or name_m3u != self.name_m3u:
            service.save_manager.set_m3u_dir(path_m3u)
            service.save_manager.set_m3u_name(name_m3u)
            service.save_manager.start_saving(m3u=True, epg=False, if_not_exists=True)
            self.path_m3u = path_m3u
            self.name_m3u = name_m3u

        cancel_epg_saving = None
        path_epg = service.addon.getSetting('path_epg')
        name_epg = service.addon.getSetting('name_epg')
        if path_epg != self.path_epg or name_epg != self.name_epg:
            if service.save_manager.check_epg():
                loc_str_1 = service.addon.getLocalizedString(30114) # 'Warning'
                loc_str_2 = service.addon.getLocalizedString(30115) # 'This will cancel the EPG save process that is not yet complete. Continue?'
                loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
                loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
                cancel_epg_saving = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
            if cancel_epg_saving == False:
                service.addon.setSetting('path_epg', self.path_epg)
                service.addon.setSetting('name_epg', self.name_epg)
                return
            service.save_manager.set_epg_dir(path_epg)
            service.save_manager.set_epg_name(name_epg)
            service.save_manager.start_saving(m3u=False, epg=True, if_not_exists=True)
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
            if service.save_manager.check_epg() and cancel_epg_saving is None:
                loc_str_1 = service.addon.getLocalizedString(30114) # 'Warning'
                loc_str_2 = service.addon.getLocalizedString(30115) # 'This will cancel the EPG save process that is not yet complete. Continue?'
                loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
                loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
                cancel_epg_saving = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
            if cancel_epg_saving == False:
                service.addon.setSetting('locale', self.locale)
                return
            # are we need send request?
            if service.get_session_status() != SessionStatus.EMPTY:
                service.request.change_locale(session_id, locale)
            service.request.headers['x-vidmind-locale'] = locale
            self.locale = locale
            service.save_manager.start_saving()

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
            service.save_manager.start_saving(m3u=True, epg=False)
            self.m3u_include_kyivstar_groups = m3u_include_kyivstar_groups

        m3u_include_favorites_group = service.addon.getSetting('m3u_include_favorites_group')
        if m3u_include_favorites_group != self.m3u_include_favorites_group:
            service.save_manager.start_saving(m3u=True, epg=False)
            self.m3u_include_favorites_group = m3u_include_favorites_group

class KyivstarService:
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

        self.save_manager = SaveManager()
        self.save_manager.set_m3u_dir(self.addon.getSetting('path_m3u'))
        self.save_manager.set_m3u_name(self.addon.getSetting('name_m3u'))
        self.save_manager.set_epg_dir(self.addon.getSetting('path_epg'))
        self.save_manager.set_epg_name(self.addon.getSetting('name_epg'))

    def set_session_status(self, status):
        window = xbmcgui.Window(10000)
        window.setProperty("KyivstarService_session_status", status)
        xbmc.log("KyivstarService: Session status changed to %s" % status, xbmc.LOGDEBUG)

    def get_session_status(self):
        window = xbmcgui.Window(10000)
        return window.getProperty("KyivstarService_session_status")

    def check_session_status(self):
        session_id = self.addon.getSetting('session_id')
        user_if = self.addon.getSetting('user_id')
        if session_id == '':
            self.set_session_status(SessionStatus.EMPTY)
        elif user_if == 'anonymous':
            profile = self.request.login_anonymous()
            if 'userId' not in profile or 'sessionId' not in profile:
                self.set_session_status(SessionStatus.INACTIVE)
                return
            self.addon.setSetting('session_id', profile['sessionId'])
            self.set_session_status(SessionStatus.ACTIVE)
        elif len(self.request.get_profiles(session_id)) > 0:
            self.set_session_status(SessionStatus.ACTIVE)
        else:
            self.set_session_status(SessionStatus.INACTIVE)

    def get_enabled_channels(self):
        if self.get_session_status() == SessionStatus.EMPTY:
            return []

        if self.save_manager.m3u_path is None:
            return []

        channel_manager = ChannelManager()
        channel_manager.load(self.save_manager.m3u_path)

        return channel_manager.enabled

    def check_m3u(self):
        if not self.save_manager.m3u_start_saving:
            return False

        loc_str = None
        if self.get_session_status() == SessionStatus.EMPTY:
            loc_str = self.addon.getLocalizedString(30204) # 'Log in to the plugin'
        elif self.save_manager.m3u_path is None:
            loc_str = self.addon.getLocalizedString(30206) # 'To save M3U list you must set path and name of file in settings.'

        if loc_str is not None:
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            self.save_manager.m3u_start_saving = False
            return False

        return True

    def check_epg(self):
        if self.save_manager.check_epg():
            return True

        if not self.save_manager.epg_start_saving:
            return False

        loc_str = None
        if self.get_session_status() == SessionStatus.EMPTY:
            loc_str = self.addon.getLocalizedString(30204) # 'Log in to the plugin'
        elif self.save_manager.m3u_path is None:
            loc_str = self.addon.getLocalizedString(30209) # 'M3U list does not exists.'
        elif not xbmcvfs.exists(self.save_manager.m3u_path):
            loc_str = self.addon.getLocalizedString(30209) # 'M3U list does not exists.'
        elif self.save_manager.epg_path is None:
            loc_str = self.addon.getLocalizedString(30210) # 'To save EPG you must set path and name of file in settings.'

        if loc_str is not None:
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            self.save_manager.epg_start_saving = False
            return False

        return True

    def restart_iptv_simple(self):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
        time.sleep(1)
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')

    def run(self):
        monitor = KyivstarServiceMonitor(self)
        self.channel_manager = ChannelManager()

        self.archive_manager = ArchiveManager()
        uset_data_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.archive_manager.open(uset_data_path)
        self.archive_manager.check_channels(True)
        self.archive_manager.check_programs(True)

        check_session_timer = 0
        check_session_wait_time = 5
        self.check_session_status()

        if self.get_session_status() == SessionStatus.INACTIVE:
            loc_str = self.addon.getLocalizedString(30212) # 'Error during session status check. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            check_session_timer = int(time.time()) + check_session_wait_time
            check_session_wait_time += 5

        if self.get_session_status() != SessionStatus.EMPTY:
            self.save_manager.start_saving(if_not_exists=True)

        self.live_stream_server = KyivstarHttpServer(self)
        self.live_stream_server.start()

        while not monitor.abortRequested():
            try:
                if self.get_session_status() == SessionStatus.INACTIVE:
                    if int(time.time()) >= check_session_timer:
                        self.check_session_status()
                        check_session_timer = int(time.time()) + check_session_wait_time
                        if check_session_wait_time < 300:
                            check_session_wait_time += 5
                    elif monitor.waitForAbort(check_session_timer - int(time.time())):
                        break
                    continue
                else:
                    check_session_wait_time = 5

                self.save_manager.check_refresh_epg(int(self.addon.getSetting('epg_refresh_hour')))

                if self.check_m3u() and self.save_manager.check_m3u():
                    if self.save_manager.process_m3u(self):
                        if self.addon.getSetting('iptv_sc_reload_when_m3u_saved') == 'true':
                            self.restart_iptv_simple()
                        loc_str = self.addon.getLocalizedString(30208) # 'Save M3U completed.'
                        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
                    else:
                        loc_str = self.addon.getLocalizedString(30207) # 'Error during list saving. Check your logs for details.'
                        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
                        self.set_session_status(SessionStatus.INACTIVE)
                elif self.check_epg() and self.save_manager.check_epg(True):
                    for _ in range(int(self.addon.getSetting('epg_group_requests_count'))):
                        if self.save_manager.process_epg(self):
                            if self.addon.getSetting('iptv_sc_reload_when_epg_saved') == 'true':
                                self.restart_iptv_simple()
                            loc_str = self.addon.getLocalizedString(30211) # 'Save EPG completed.'
                            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
                            break
                elif self.archive_manager.check_channels():
                    for _ in range(int(self.addon.getSetting('epg_group_requests_count'))):
                        self.archive_manager.process_channel(self)
                elif self.archive_manager.check_programs():
                    for _ in range(int(self.addon.getSetting('epg_group_requests_count'))):
                        self.archive_manager.process_program(self)

                wait_time = 60
                if self.save_manager.check_epg() or self.archive_manager.check_programs() or self.archive_manager.check_channels():
                    wait_time = int(self.addon.getSetting('epg_group_requests_delay'))
                if monitor.waitForAbort(wait_time):
                    break

            except Exception as e:
                xbmc.log("KyivstarService exception: %s" % str(e), xbmc.LOGERROR)
                xbmc.log("KyivstarService call trace: %s" % (traceback.format_exc()), xbmc.LOGERROR)

        self.archive_manager.close()
        self.live_stream_server.stop()
        if self.channel_manager.changed and self.addon.getSetting('autosave_changes_on_exit') == 'true':
            if self.save_manager.m3u_path is None:
                return
            self.channel_manager.save(self.save_manager.m3u_path)
