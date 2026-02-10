import os
import xml.etree.ElementTree as etree

from collections import deque
from datetime import datetime, timedelta, timezone

import xbmc
import xbmcgui
import xbmcvfs

from resources.lib.channel_manager import ChannelManager
from resources.lib.common import strip_html, SessionStatus

class Task(object):
    SCHEDULED = -2
    NORMAL = -1
    CHECK_STATUS = 0
    RESET_ARCHIVE = 1
    SET_ARCHIVE_CHANNELS = 2
    SAVE_M3U = 3
    SAVE_EPG = 4
    UNIQUE_TASK_COUNT = 5

    def __init__(self, name=None):
        self.name = name or self.__class__.__name__
        self.start_time = None
        self._wait_timer = None
        self._running_value = False

    def unique(self):
        return Task.NORMAL

    def run(self, service):
        if self.start_time is None:
            self._running_value = True
            self.start_time = datetime.now()
            xbmc.log("KyivstarService: Task %s started." % self.name, xbmc.LOGDEBUG)

        now = datetime.now()
        if self._wait_timer is not None and self._wait_timer > now:
            return (self._wait_timer - now).total_seconds()

        wait_time = self._run_internal(service)

        if self.finished():
            self._running_value = False
            duration = datetime.now() - self.start_time
            xbmc.log("KyivstarService: Task %s completed. Duration: %s" % (self.name, duration), xbmc.LOGDEBUG)
        self._wait_timer = datetime.now() + timedelta(seconds=wait_time or 0)
        return wait_time

    def _run_internal(self, service):
        raise NotImplementedError("_run_internal() must be implemented by subclasses")

    def running(self):
        return self._running_value

    def finished(self):
        return True

class TaskQueue(object):
    def __init__(self):
        self.normal_tasks = deque()
        self.unique_tasks = [None] * Task.UNIQUE_TASK_COUNT
        self.scheduled_tasks = []

    def add(self, task):
        if not isinstance(task, Task):
            raise TypeError("task must be instance of Task")

        unique_idx = task.unique()
        if unique_idx == Task.NORMAL:
            self.normal_tasks.append(task)
        elif unique_idx == Task.SCHEDULED:
            self.scheduled_tasks.append(task)
        else:
            self.unique_tasks[unique_idx] = task

    def get_unique_task(self, unique_idx):
        if unique_idx >= Task.UNIQUE_TASK_COUNT or unique_idx <= Task.NORMAL:
            return None

        return self.unique_tasks[unique_idx]

    def _min(self, *args):
        result = None
        for arg in args:
            if arg is None:
                continue
            elif result is None:
                result = arg
            else:
                result = min(result, arg)
        return result

    def run_one(self, service):
        wait_time = None
        for task in self.scheduled_tasks:
            wait_time = self._min(wait_time, task.run(service))

        for idx, task in enumerate(self.unique_tasks):
            if task is None:
                continue
            wait_time = self._min(wait_time, task.run(service))
            if task.finished():
                self.unique_tasks[idx] = None
            return wait_time

        if len(self.normal_tasks) == 0:
            return wait_time

        task = self.normal_tasks[0]
        wait_time = self._min(wait_time, task.run(service))
        if task.finished():
            self.normal_tasks.popleft()
        return wait_time

class CheckSessionStatusTask(Task):
    def __init__(self, name="CheckSessionStatusTask"):
        super(CheckSessionStatusTask, self).__init__(name=name)
        self._finished_value = False
        self._wait_time = 0

    def unique(self):
        return Task.CHECK_STATUS

    def _run_internal(self, service):
        if service.get_session_status() != SessionStatus.INACTIVE:
            self._finished_value = True
            return 0

        service.check_session_status()
        if service.get_session_status() == SessionStatus.INACTIVE:
            if self._wait_time == 0:
                loc_str = service.addon.getLocalizedString(30212) # 'Error during session status check. Check your logs for details.'
                xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            self._wait_time = min(300, self._wait_time + 5)
        else:
            self._finished_value = True
            self._wait_time = 0
        return self._wait_time

    def finished(self):
        return self._finished_value

class UpdateArchiveTask(Task):
    def __init__(self, name="UpdateArchiveTask"):
        super(UpdateArchiveTask, self).__init__(name=name)
        self._finished_value = False

    def _run_internal(self, service):
        archive_manager = service.archive_manager
        if archive_manager.check_channels():
            archive_manager.process_channel(service)
        elif archive_manager.check_programs():
            archive_manager.process_program(service)

        if not archive_manager.check_channels() and not archive_manager.check_programs():
            self._finished_value = True
        return int(service.addon.getSetting('epg_group_requests_delay'))

    def finished(self):
        return self._finished_value

class ResetArchiveTask(Task):
    def __init__(self, name="ResetArchiveTask"):
        super(ResetArchiveTask, self).__init__(name=name)

    def unique(self):
        return Task.RESET_ARCHIVE

    def _run_internal(self, service):
        service.archive_manager.reset()
        return 0

class SetArchiveChannelsTask(Task):
    def __init__(self, archive_channels, name="SetArchiveChannelsTask"):
        super(SetArchiveChannelsTask, self).__init__(name=name)
        self.archive_channels = archive_channels

    def unique(self):
        return Task.SET_ARCHIVE_CHANNELS

    def _run_internal(self, service):
        channels = service.get_enabled_channels()
        activated_channel_ids = set(service.archive_manager.get_channels())
        channel_ids = set(self.archive_channels)
        archive_manager = service.archive_manager

        has_disabled = False
        for channel in channels:
            if channel.id in channel_ids and channel.id not in activated_channel_ids:
                archive_manager.enable_channel(channel)
            elif channel.id not in channel_ids and channel.id in activated_channel_ids:
                archive_manager.disable_channel(channel.id)
                has_disabled = True
        archive_manager.check_channels(True)
        if has_disabled:
            archive_manager.check_programs(True)
            archive_manager.vacuum()

        service.tasks.add(UpdateArchiveTask())
        return 0

class SaveM3UTask(Task):
    def __init__(self, path, update=False, save=True, channel_manager=None, name="SaveM3UTask"):
        super(SaveM3UTask, self).__init__(name=name)
        self.path = path
        self.update = update
        self.save = save
        self.channel_manager = channel_manager

    def unique(self):
        return Task.SAVE_M3U

    def _run_internal(self, service):
        loc_str = None
        if service.get_session_status() == SessionStatus.EMPTY:
            loc_str = service.addon.getLocalizedString(30204) # 'Log in to the plugin'
        elif self.path is None:
            loc_str = service.addon.getLocalizedString(30206) # 'To save M3U list you must set path and name of file in settings.'
        if loc_str is not None:
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            return 0

        channel_manager = self.channel_manager or ChannelManager()

        if self.update:
            channel_manager.reset()
            channel_manager.load(self.path)

        if not channel_manager.download(service):
            loc_str = service.addon.getLocalizedString(30207) # 'Error during list saving. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            service.set_session_status(SessionStatus.INACTIVE)
            return 0

        if self.update and channel_manager.changed:
            loc_str = service.addon.getLocalizedString(30218) # 'Channel updates: %s added, %s removed.'
            loc_str = loc_str % (len(channel_manager.new), len(channel_manager.removed))
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)

        if not self.save:
            return 1

        temp = os.path.join(xbmcvfs.translatePath('special://temp'), 'temp.m3u')

        channel_manager.save(temp)

        xbmcvfs.copy(temp, self.path)
        xbmcvfs.delete(temp)

        if service.addon.getSetting('iptv_sc_reload_when_m3u_saved') == 'true':
            service.restart_iptv_simple()

        loc_str = service.addon.getLocalizedString(30208) # 'Save M3U completed.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
        return 1

class SaveEPGTask(Task):
    def __init__(self, path, name="SaveEPGTask"):
        super(SaveEPGTask, self).__init__(name=name)
        self.path = path

        self.xml_root = None
        self.channels = None
        self._finished_value = False

    def unique(self):
        return Task.SAVE_EPG

    def _load_xml_root(self):
        if self.path is None or not xbmcvfs.exists(self.path):
            return etree.Element("tv")
        try:
            f = xbmcvfs.File(self.path)
            data = f.read()
            f.close()
            xml_root = etree.fromstring(data)
            if xml_root.tag == 'tv':
                return xml_root
        except Exception as e:
            xbmc.log("KyivstarService: Failed to load existing EPG: %s" % str(e), xbmc.LOGERROR)
        return etree.Element("tv")

    def _load_channels(self, path):
        channel_manager = ChannelManager()
        try:
            channel_manager.load(path)
        except Exception as e:
            xbmc.log("KyivstarService: Failed to load channels for EPG: %s" % str(e), xbmc.LOGERROR)
            return []

        xml_channels = { xml_channel.get('id') : xml_channel for xml_channel in self.xml_root.findall(".//channel") }
        for channel_id, xml_channel in xml_channels.items():
            if channel_id in channel_manager.all and channel_manager.all[channel_id].enabled:
                continue
            self.xml_root.remove(xml_channel)
            for xml_programme in self.xml_root.findall(".//programme[@channel='%s']" % channel_id):
                self.xml_root.remove(xml_programme)

        for channel in channel_manager.enabled:
            if channel.id in xml_channels:
                xml_channel = xml_channels[channel.id]
                xml_channel.find("display-name").text = channel.name
                xml_channel.find("icon").set("src", channel.logo)
            else:
                xml_channel = etree.SubElement(self.xml_root, "channel", attrib={"id": channel.id})
                etree.SubElement(xml_channel, "display-name").text = channel.name
                etree.SubElement(xml_channel, "icon", src=channel.logo)

        return channel_manager.enabled

    def _parse_time(self, time_str):
        if not time_str:
            return None
        try:
            return datetime.strptime(time_str, '%Y%m%d%H%M%S %z')
        except Exception:
            try:
                return datetime.strptime(time_str, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            except Exception:
                return None

    def _group_programmes(self, programmes):
        groups = {}
        for p in programmes:
            dt = self._parse_time(p.get("start"))
            if dt is None:
                groups.setdefault('removed', []).append(p)
            else:
                dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                groups.setdefault(dt, []).append(p)
        return groups

    def _process_epg(self, service):
        session_id = service.addon.getSetting('session_id')

        channel = self.channels.pop(0)

        day_programmes = self._group_programmes(self.xml_root.findall(".//programme[@channel='%s']" % channel.id))
        for p in day_programmes.pop('removed', []):
            self.xml_root.remove(p)

        try:
            now = datetime.now(timezone.utc)
        except Exception:
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
        threshold = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=3)

        to_remove = []
        for day, programmes in day_programmes.items():
            if day >= threshold:
                continue
            for p in programmes:
                self.xml_root.remove(p)
            to_remove.append(day)
        for day in to_remove:
            del day_programmes[day]

        epg_data = service.request.get_elem_epg_data(session_id, channel.id)

        if service.request.error:
            if service.request.recoverable:
                xbmc.log("KyivstarService step_save_epg: recoverable error occurred while downloading asset %s(%s) epg data." % (channel.id, channel.name), xbmc.LOGDEBUG)
                service.set_session_status(SessionStatus.INACTIVE)
                self.channels.append(channel)
                return
            else:
                xbmc.log("KyivstarService step_save_epg: error occurred while downloading asset %s(%s) epg data." % (channel.id, channel.name), xbmc.LOGERROR)
                return

        if len(epg_data) == 0:
            xbmc.log("KyivstarService step_save_epg: asset %s(%s) does not have epg data." % (channel.id, channel.name), xbmc.LOGDEBUG)
            return

        service.archive_manager.update_programs(channel, epg_data)

        for epg_day_data in epg_data:
            program_list = epg_day_data.get('programList', [])

            if program_list:
                day_date = datetime.fromtimestamp(epg_day_data['date']/1000, tz=timezone.utc)
                day_date = day_date.replace(hour=0, minute=0, second=0, microsecond=0)
                for p in day_programmes.get(day_date, []):
                    self.xml_root.remove(p)

            for program in program_list:
                program_attrib = {
                    "start": datetime.fromtimestamp(program['start']/1000, tz=timezone.utc).strftime('%Y%m%d%H%M%S %z'),
                    "stop": datetime.fromtimestamp(program['finish']/1000, tz=timezone.utc).strftime('%Y%m%d%H%M%S %z'),
                    "channel": channel.id
                }
                if channel.catchup and channel.type == 'VIRTUAL':
                    program_attrib['catchup-id'] = str(int(program['start']/1000))
                xml_program = etree.SubElement(self.xml_root, "programme", attrib=program_attrib)
                etree.SubElement(xml_program, "title").text = program['title']
                if service.addon.getSetting('epg_include_description') == 'true':
                    etree.SubElement(xml_program, "desc").text = strip_html(program['desc'])

    def _save_epg(self):
        tree = etree.ElementTree(self.xml_root)
        etree.indent(tree, space="  ", level=0)

        data = '<?xml version="1.0" encoding="utf-8"?>\n'.encode('utf-8') + etree.tostring(self.xml_root, encoding='utf-8')

        f = xbmcvfs.File(self.path, 'w')
        f.write(data)
        f.close()

    def _run_internal(self, service):
        loc_str = None
        if service.get_session_status() == SessionStatus.EMPTY:
            loc_str = service.addon.getLocalizedString(30204) # 'Log in to the plugin'
        elif service.m3u_path is None:
            loc_str = service.addon.getLocalizedString(30209) # 'M3U list does not exists.'
        elif not xbmcvfs.exists(service.m3u_path):
            loc_str = service.addon.getLocalizedString(30209) # 'M3U list does not exists.'
        elif self.path is None:
            loc_str = service.addon.getLocalizedString(30210) # 'To save EPG you must set path and name of file in settings.'
        if loc_str is not None:
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
            self._finished_value = True
            return 0

        if self.xml_root is None:
            self.xml_root = self._load_xml_root()
        if self.channels is None:
            self.channels = self._load_channels(service.m3u_path)

        for _ in range(int(service.addon.getSetting('epg_group_requests_count'))):
            if len(self.channels) > 0:
                self._process_epg(service)

        wait_time = int(service.addon.getSetting('epg_group_requests_delay'))

        if len(self.channels) > 0:
            return wait_time

        self._save_epg()

        service.archive_manager.check_channels(True)
        service.archive_manager.check_programs(True)
        service.tasks.add(UpdateArchiveTask())

        if service.addon.getSetting('iptv_sc_reload_when_epg_saved') == 'true':
            service.restart_iptv_simple()

        loc_str = service.addon.getLocalizedString(30211) # 'Save EPG completed.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)

        self._finished_value = True
        return wait_time

    def finished(self):
        return self._finished_value

class DailySaveM3UTask(Task):
    def __init__(self, name="DailySaveM3UTask"):
        super(DailySaveM3UTask, self).__init__(name=name)
        self.refresh_timer = None

    def unique(self):
        return Task.SCHEDULED

    def _run_internal(self, service):
        if service.get_session_status() == SessionStatus.EMPTY:
            return None

        if service.m3u_path is None:
            return None

        task = service.tasks.get_unique_task(Task.SAVE_M3U)
        if task and task.running():
            return None

        refresh_enable = service.addon.getSetting('m3u_refresh_enable') == 'true'
        refresh_hour = int(service.addon.getSetting('m3u_refresh_hour'))
        if not refresh_enable:
            if self.refresh_timer is None:
                if xbmcvfs.exists(service.m3u_path):
                    st = xbmcvfs.Stat(service.m3u_path)
                    self.refresh_timer = datetime.fromtimestamp(st.st_mtime())
                else:
                    service.tasks.add(SaveM3UTask(service.m3u_path))
                    self.refresh_timer = datetime.now()
                self.refresh_timer = self.refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
                self.refresh_timer += timedelta(days=1)
            return None

        if self.refresh_timer and self.refresh_timer > datetime.now():
            remaining = self.refresh_timer - datetime.now()
            return max(0, int(remaining.total_seconds()))

        if self.refresh_timer is None and xbmcvfs.exists(service.m3u_path):
            st = xbmcvfs.Stat(service.m3u_path)
            self.refresh_timer = datetime.fromtimestamp(st.st_mtime())
            self.refresh_timer = self.refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
            self.refresh_timer += timedelta(days=1)
            remaining = self.refresh_timer - datetime.now()
            return max(0, int(remaining.total_seconds()))

        refresh_save = service.addon.getSetting('m3u_refresh_save') == 'true'
        service.tasks.add(SaveM3UTask(service.m3u_path, update=True, save=refresh_save, channel_manager=service.channel_manager))
        self.refresh_timer = datetime.now()
        self.refresh_timer = self.refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
        self.refresh_timer += timedelta(days=1)
        xbmc.log("KyivstarService: m3u updating, next refresh date is %s" % self.refresh_timer.strftime("%Y-%m-%d %H:%M:%S"), xbmc.LOGDEBUG)
        remaining = self.refresh_timer - datetime.now()
        return max(0, int(remaining.total_seconds()))

    def finished(self):
        return False

class DailySaveEPGTask(Task):
    def __init__(self, name="DailySaveEPGTask"):
        super(DailySaveEPGTask, self).__init__(name=name)
        self.refresh_timer = None

    def unique(self):
        return Task.SCHEDULED

    def _run_internal(self, service):
        if service.get_session_status() == SessionStatus.EMPTY:
            return None

        if service.epg_path is None:
            return None

        task = service.tasks.get_unique_task(Task.SAVE_EPG)
        if task and task.running():
            return None

        refresh_hour = int(service.addon.getSetting('epg_refresh_hour'))
        if self.refresh_timer is None and xbmcvfs.exists(service.epg_path):
            st = xbmcvfs.Stat(service.epg_path)
            self.refresh_timer = datetime.fromtimestamp(st.st_mtime())
            self.refresh_timer = self.refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
            self.refresh_timer += timedelta(days=1)
            remaining = self.refresh_timer - datetime.now()
            return max(0, int(remaining.total_seconds()))

        service.tasks.add(SaveEPGTask(service.epg_path))
        self.refresh_timer = datetime.now()
        self.refresh_timer = self.refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
        self.refresh_timer += timedelta(days=1)
        xbmc.log("KyivstarService: epg updating, next refresh date is %s" % self.refresh_timer.strftime("%Y-%m-%d %H:%M:%S"), xbmc.LOGDEBUG)
        remaining = self.refresh_timer - datetime.now()
        return max(0, int(remaining.total_seconds()))

    def finished(self):
        return False
