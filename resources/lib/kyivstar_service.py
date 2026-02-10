import os
import threading
import uuid

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.kyivstar_request import KyivstarRequest
from resources.lib.kyivstar_http_server import KyivstarHttpServer
from resources.lib.channel_manager import ChannelManager
from resources.lib.archive_manager import ArchiveManager
from resources.lib.tasks import Task, TaskQueue, CheckSessionStatusTask, SaveM3UTask, SaveEPGTask, DailySaveEPGTask, DailySaveM3UTask
from resources.lib.common import strip_html, SessionStatus

class KyivstarServiceMonitor(xbmc.Monitor):
    def __init__(self, service):
        xbmc.Monitor.__init__(self)

        self.service = service
        self.settings = [
            { 'name' : ('path_m3u', 'name_m3u'), 'func' : self.set_m3u_path },
            { 'name' : ('path_epg', 'name_epg'), 'func' : self.set_epg_path },
            { 'name' : ('stream_inputstream',), 'func' : self.set_inputstream },
            { 'name' : ('locale',), 'func' : self.set_locale },
            { 'name' : ('live_stream_server_port',), 'func' : self.set_server_port },
            { 'name' : ('m3u_include_kyivstar_groups',), 'func' : self.set_groups },
            { 'name' : ('m3u_include_favorites_group',), 'func' : self.set_groups }
        ]
        self.cancel_epg_saving = None
        self.load_setting_values('_value')

    def load_setting_values(self, prop):
        for setting in self.settings:
            for name in setting['name']:
                setting[name + prop] = self.service.addon.getSetting(name)

    def show_cancel_epg_saving(self):
        if self.cancel_epg_saving is None:
            loc_str_1 = self.service.addon.getLocalizedString(30114) # 'Warning'
            loc_str_2 = self.service.addon.getLocalizedString(30115) # 'This will cancel the EPG save process that is not yet complete. Continue?'
            loc_str_3 = self.service.addon.getLocalizedString(30112) # 'Yes'
            loc_str_4 = self.service.addon.getLocalizedString(30113) # 'No'
            self.cancel_epg_saving = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
        return self.cancel_epg_saving

    def check_setting(self, setting):
        changed = False
        for name in setting['name']:
            if setting[name + '_value'] != setting[name + '_new_value']:
                changed = True
                break

        if not changed:
            return

        if setting['func'](setting):
            for name in setting['name']:
                setting[name + '_value'] = setting[name + '_new_value']
        else:
            for name in setting['name']:
                self.service.addon.setSetting(name, setting[name + '_value'])

    def set_m3u_path(self, setting):
        service = self.service
        service.set_m3u_path(setting['path_m3u_new_value'], setting['name_m3u_new_value'])
        if service.m3u_path and not xbmcvfs.exists(service.m3u_path):
            service.add_task(SaveM3UTask(service.m3u_path))
        return True

    def set_epg_path(self, setting):
        service = self.service
        if service.tasks.get_unique_task(Task.SAVE_EPG) and not self.show_cancel_epg_saving():
            return False
        service.set_epg_path(setting['path_epg_new_value'], setting['name_epg_new_value'])
        if service.epg_path and not xbmcvfs.exists(service.epg_path):
            service.add_task(SaveEPGTask(service.epg_path))
        return True

    def check_inputstream(self, inputstream):
        if inputstream == 'default':
            return True
        if xbmc.getCondVisibility('System.HasAddon(%s)' % inputstream) == 0:
            loc_str = self.service.addon.getLocalizedString(30213) # 'Inputstream addon does not found. Set value to default.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return False
        return True

    def set_inputstream(self, setting):
        return self.check_inputstream(setting['stream_inputstream_new_value'])

    def set_locale(self, setting):
        service = self.service
        if service.tasks.get_unique_task(Task.SAVE_EPG) and not self.show_cancel_epg_saving():
            return False
        # are we need send request?
        locale = setting['locale_new_value']
        session_id = self.service.addon.getSetting('session_id')
        if service.get_session_status() != SessionStatus.EMPTY:
            service.request.change_locale(session_id, locale)
        service.request.headers['x-vidmind-locale'] = locale
        if service.m3u_path: service.add_task(SaveM3UTask(service.m3u_path))
        if service.epg_path: service.add_task(SaveEPGTask(service.epg_path))
        return True

    def set_server_port(self, setting):
        self.service.live_stream_server.stop()
        port = setting['live_stream_server_port_new_value']
        self.service.request.set_base_local_url_port(port)
        self.service.live_stream_server.start()
        return True

    def set_groups(self, setting):
        service = self.service
        if service.m3u_path: service.add_task(SaveM3UTask(service.m3u_path))
        return True

    def onSettingsChanged(self):
        self.cancel_epg_saving = None
        self.load_setting_values('_new_value')

        for setting in self.settings:
            self.check_setting(setting)

class KyivstarService:
    def __init__(self):
        self.addon = xbmcaddon.Addon()

        device_id = self.addon.getSetting('device_id')
        if not device_id:
            self.addon.setSetting('device_id', str(uuid.uuid4()))

        locale = self.addon.getSetting('locale')

        self.request = KyivstarRequest(device_id, locale)
        self.request.set_base_local_url_port(self.addon.getSetting('live_stream_server_port'))

        self.set_m3u_path()
        self.set_epg_path()

    def set_m3u_path(self, dirname=None, filename=None):
        self.m3u_path = None
        if dirname is None:
            dirname = self.addon.getSetting('path_m3u')
        if filename is None:
            filename = self.addon.getSetting('name_m3u')
        if dirname != '' and filename != '':
            self.m3u_path = os.path.join(dirname, filename)

    def set_epg_path(self, dirname=None, filename=None):
        self.epg_path = None
        if dirname is None:
            dirname = self.addon.getSetting('path_epg')
        if filename is None:
            filename = self.addon.getSetting('name_epg')
        if dirname != '' and filename != '':
            self.epg_path = os.path.join(dirname, filename)

    def set_session_status(self, status):
        window = xbmcgui.Window(10000)
        window.setProperty("KyivstarService_session_status", status)
        xbmc.log("KyivstarService: Session status changed to %s" % status, xbmc.LOGDEBUG)

        if status == SessionStatus.INACTIVE and hasattr(self, 'tasks'):
            if self.tasks.get_unique_task(Task.CHECK_STATUS):
                return
            self.add_task(CheckSessionStatusTask())

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

        if self.m3u_path is None:
            return []

        channel_manager = ChannelManager()
        channel_manager.load(self.m3u_path)

        return channel_manager.enabled

    def restart_iptv_simple(self):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
        xbmc.sleep(1000)
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')

    def add_task(self, task):
        if task is None:
            return

        self.tasks.add(task)
        self.loop_event.set()

    def loop(self):
        self.check_session_status()

        self.add_task(DailySaveEPGTask())
        self.add_task(DailySaveM3UTask())

        while not self.abort_requested:
            self.loop_event.wait(self.tasks.run_one(self))
            self.loop_event.clear()

    def run(self):
        self.abort_requested = False
        self.loop_event = threading.Event()
        self.tasks = TaskQueue()

        monitor = KyivstarServiceMonitor(self)
        self.channel_manager = ChannelManager()

        self.archive_manager = ArchiveManager()
        user_data_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.archive_manager.open(user_data_path)
        self.archive_manager.check_channels(True)
        self.archive_manager.check_programs(True)

        self.live_stream_server = KyivstarHttpServer(self)
        self.live_stream_server.start()

        loop_thread = threading.Thread(target=self.loop)
        loop_thread.start()

        monitor.waitForAbort()

        self.abort_requested = True
        self.loop_event.set()
        loop_thread.join()

        self.live_stream_server.stop()
        self.archive_manager.close()
        if self.channel_manager.changed and self.addon.getSetting('autosave_changes_on_exit') == 'true':
            if self.m3u_path is None:
                return
            self.channel_manager.save(self.m3u_path)
