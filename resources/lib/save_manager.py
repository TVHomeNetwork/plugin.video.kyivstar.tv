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
        self.m3u_start_saving = False

        self.epg_dir = ''
        self.epg_name = ''
        self.epg_path = None
        self.epg_start_saving = False

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

    def start_saving(self, m3u=True, epg=True, if_not_exists=False):
        if m3u and self.m3u_path is not None and (not if_not_exists or if_not_exists and not xbmcvfs.exists(self.m3u_path)):
            self.m3u_start_saving = True
        if epg and self.epg_path is not None and (not if_not_exists or if_not_exists and not xbmcvfs.exists(self.epg_path)):
            self.epg_start_saving = True

    def check_m3u(self):
        return self.m3u_start_saving

    def process_m3u(self, service):
        xbmc.log("KyivstarService: Saving M3U started.", xbmc.LOGDEBUG)

        channel_manager = ChannelManager()

        if not channel_manager.download(service):
            return False

        # If we write data stright to the 'self.m3u_path' file, pvr.iptvsimple can stuck on updating channels.
        temp = os.path.join(xbmcvfs.translatePath('special://temp'), 'temp.m3u')

        channel_manager.save(temp)

        xbmcvfs.copy(temp, self.m3u_path)
        xbmcvfs.delete(temp)

        xbmc.log("KyivstarService: Saving M3U completed.", xbmc.LOGDEBUG)

        self.m3u_start_saving = False
        return True

    def check_refresh_epg(self, refresh_hour):
        if self.check_epg():
            return

        if self.epg_path is None:
            return

        if self.epg_refresh_timer and datetime.now() < self.epg_refresh_timer:
            return

        if not xbmcvfs.exists(self.epg_path):
            self.epg_start_saving = True
            xbmc.log("KyivstarService: epg does not exists, creating new one", xbmc.LOGDEBUG)
            return

        if self.epg_refresh_timer is None:
            st = xbmcvfs.Stat(self.epg_path)
            self.epg_refresh_timer = datetime.fromtimestamp(st.st_mtime())
            self.epg_refresh_timer = self.epg_refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
            self.epg_refresh_timer += timedelta(days=1)

        if datetime.now() < self.epg_refresh_timer:
            return

        self.epg_start_saving = True
        self.epg_refresh_timer = datetime.now()
        self.epg_refresh_timer = self.epg_refresh_timer.replace(hour=refresh_hour, minute=0, second=0, microsecond=0)
        self.epg_refresh_timer += timedelta(days=1)
        xbmc.log("KyivstarService: epg updating, next refresh date is %s" % self.epg_refresh_timer.strftime("%Y-%m-%d %H:%M:%S"), xbmc.LOGDEBUG)

    def check_epg(self, load = False):
        if self.epg_start_saving and load:
            self.epg_start_saving = False

            if len(self.epg_channels) > 0:
                self.epg_channels = []

            xbmc.log("KyivstarService: Saving EPG started.", xbmc.LOGDEBUG)

            self.epg_xml_root = etree.Element("tv")

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
            channel = channels[0]
            epg_data = service.request.get_elem_epg_data(session_id, channel.id)

            if service.request.error:
                if service.request.recoverable:
                    xbmc.log("KyivstarService step_save_epg: recoverable error occurred while downloading asset %s(%s) epg data." % (channel.id, channel.name), xbmc.LOGDEBUG)
                    service.set_session_status(SessionStatus.INACTIVE)
                    return False
                else:
                    xbmc.log("KyivstarService step_save_epg: error occurred while downloading asset %s(%s) epg data." % (channel.id, channel.name), xbmc.LOGERROR)
                    del channels[0]
                    return False

            if len(epg_data) == 0:
                xbmc.log("KyivstarService step_save_epg: asset %s(%s) does not have epg data." % (channel.id, channel.name), xbmc.LOGDEBUG)
                del channels[0]
                return False

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
            del channels[0]
            return False

        tree = etree.ElementTree(xml_root)
        etree.indent(tree, space="  ", level=0)

        epg_list = '<?xml version="1.0" encoding="utf-8"?>\n'.encode("utf-8") + etree.tostring(xml_root, encoding='utf-8')

        f = xbmcvfs.File(self.epg_path, 'w')
        f.write(epg_list)
        f.close()

        self.epg_xml_root = None

        service.archive_manager.check_channels(True)
        service.archive_manager.check_programs(True)

        xbmc.log("KyivstarService: Saving EPG completed.", xbmc.LOGDEBUG)
        return True
