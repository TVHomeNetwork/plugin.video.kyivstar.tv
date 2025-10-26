import os
from datetime import datetime, timedelta, timezone

import xbmc
import xbmcvfs

import xml.etree.ElementTree as etree

from resources.lib.channel_manager import ChannelManager
from resources.lib.common import strip_html, SessionStatus

class SaveManager():
    def __init__(self):
        self.m3u_dir = ''
        self.m3u_name = ''
        self.m3u_path = None

        self.epg_dir = ''
        self.epg_name = ''
        self.epg_path = None

        self.process_m3u_path = None
        self.process_epg_path = None
        self.epg_channels = []
        self.epg_xml_root = None

        self.epg_refresh_timer = None

    def update_m3u_path(self):
        self.m3u_path = None
        if self.m3u_dir != '' and self.m3u_name != '':
            self.m3u_path = os.path.join(self.m3u_dir, self.m3u_name)

    def set_m3u_dir(self, value):
        self.m3u_dir = value
        self.update_m3u_path()

    def set_m3u_name(self, value):
        self.m3u_name = value
        self.update_m3u_path()

    def update_epg_path(self):
        self.epg_path = None
        if self.epg_dir != '' and self.epg_name != '':
            self.epg_path = os.path.join(self.epg_dir, self.epg_name)

    def set_epg_dir(self, value):
        self.epg_dir = value
        self.update_epg_path()

    def set_epg_name(self, value):
        self.epg_name = value
        self.update_epg_path()

    def check_m3u(self, load = False):
        if load:
            self.process_m3u_path = self.m3u_path
        return load

    def process_m3u(self, service):
        xbmc.log("KyivstarService: Saving M3U started.", xbmc.LOGDEBUG)

        channel_manager = ChannelManager()

        if not channel_manager.download(service):
            return False

        # If we write data stright to the 'self.m3u_path' file, pvr.iptvsimple can stuck on updating channels.
        temp = os.path.join(xbmcvfs.translatePath('special://temp'), 'temp.m3u')

        channel_manager.save(temp)

        xbmcvfs.copy(temp, self.process_m3u_path)
        xbmcvfs.delete(temp)

        xbmc.log("KyivstarService: Saving M3U completed.", xbmc.LOGDEBUG)
        return True

    def check_refresh_epg(self, refresh_hour):
        if self.check_epg():
            return None

        if self.epg_path is None:
            return None

        if self.epg_refresh_timer:
            remaining = self.epg_refresh_timer - datetime.now()
            return max(0, int(remaining.total_seconds()))

        if not xbmcvfs.exists(self.epg_path):
            return 0

        if self.epg_refresh_timer is None:
            st = xbmcvfs.Stat(self.epg_path)
            self.epg_refresh_timer = datetime.fromtimestamp(st.st_mtime())
            self.epg_refresh_timer = self.epg_refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
            self.epg_refresh_timer += timedelta(days=1)

        now = datetime.now()
        if now < self.epg_refresh_timer:
            remaining = self.epg_refresh_timer - now
            return int(remaining.total_seconds())

        self.epg_refresh_timer = now
        self.epg_refresh_timer = self.epg_refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
        self.epg_refresh_timer += timedelta(days=1)
        xbmc.log("KyivstarService: epg updating, next refresh date is %s" % self.epg_refresh_timer.strftime("%Y-%m-%d %H:%M:%S"), xbmc.LOGDEBUG)
        return 0

    def check_epg(self, load = False):
        if load:
            xbmc.log("KyivstarService: Saving EPG started.", xbmc.LOGDEBUG)

            self.process_epg_path = self.epg_path
            self.epg_xml_root = etree.Element("tv")
            self.epg_channels = []

            channel_manager = ChannelManager()
            channel_manager.load(self.m3u_path)

            for channel in channel_manager.enabled:
                xml_channel = etree.SubElement(self.epg_xml_root, "channel", attrib={"id": channel.id})
                etree.SubElement(xml_channel, "display-name").text = channel.name
                etree.SubElement(xml_channel, "icon", src=channel.logo)
                self.epg_channels.append(channel)

        return len(self.epg_channels) > 0

    def process_epg(self, service):
        session_id = service.addon.getSetting('session_id')

        channels = self.epg_channels
        xml_root = self.epg_xml_root

        if len(channels) > 0:
            channel = channels.pop(0)
            epg_data = service.request.get_elem_epg_data(session_id, channel.id)

            if service.request.error:
                if service.request.recoverable:
                    xbmc.log("KyivstarService step_save_epg: recoverable error occurred while downloading asset %s(%s) epg data." % (channel.id, channel.name), xbmc.LOGDEBUG)
                    service.set_session_status(SessionStatus.INACTIVE)
                    channels.append(channel)
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
                for program in program_list:
                    program_attrib = {
                        "start": datetime.fromtimestamp(program['start']/1000, tz=timezone.utc).strftime('%Y%m%d%H%M%S %z'),
                        "stop": datetime.fromtimestamp(program['finish']/1000, tz=timezone.utc).strftime('%Y%m%d%H%M%S %z'),
                        "channel": channel.id
                    }
                    if channel.catchup and channel.type == 'VIRTUAL':
                        program_attrib['catchup-id'] = str(int(program['start']/1000))
                    xml_program = etree.SubElement(xml_root, "programme", attrib=program_attrib)
                    etree.SubElement(xml_program, "title").text = program['title']
                    if service.addon.getSetting('epg_include_description') == 'true':
                        etree.SubElement(xml_program, "desc").text = strip_html(program['desc'])

    def finish_epg(self, service):
        xml_root = self.epg_xml_root
        tree = etree.ElementTree(xml_root)
        etree.indent(tree, space="  ", level=0)

        epg_list = '<?xml version="1.0" encoding="utf-8"?>\n'.encode("utf-8") + etree.tostring(xml_root, encoding='utf-8')

        f = xbmcvfs.File(self.process_epg_path, 'w')
        f.write(epg_list)
        f.close()

        self.epg_xml_root = None

        service.archive_manager.check_channels(True)
        service.archive_manager.check_programs(True)

        xbmc.log("KyivstarService: Saving EPG completed.", xbmc.LOGDEBUG)
