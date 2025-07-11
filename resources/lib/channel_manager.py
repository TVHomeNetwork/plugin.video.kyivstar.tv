import re
import time

import xbmcvfs

class Channel():
    def __init__(self):
        self.id = ''
        self.name = ''
        self.logo = ''
        self.type = ''
        self.catchup = False
        self.enabled = True
        self.url = ''
        self.groups = []

    def to_dict(self):
        return {
            'id' : self.id,
            'name' : self.name,
            'logo' : self.logo,
            'type' : self.type,
            'catchup' : self.catchup,
            'enabled' : self.enabled,
            'url' : self.url,
            'groups' : self.groups
            }

    def read(self, text):
        if text.startswith('#plugin://'):
            self.enabled = False
            text = text[1:]
        if text.startswith('plugin://'):
            self.url = text
            self.type = 'VIRTUAL' if 'VIRTUAL' in text else 'IP'
            return
        match = re.search('tvg-id=".*?"', text)
        if match:
            self.id = match.group().split('"')[1]
        match = re.search('tvg-name=".*?"', text)
        if match:
            self.name = match.group().split('"')[1]
        match = re.search('tvg-logo=".*?"', text)
        if match:
            self.logo = match.group().split('"')[1]
        match = re.search('group-title=".*?"', text)
        if match:
            self.groups = match.group().split('"')[1].split(';')
        if 'catchup=' in text:
            self.catchup = True

    def write(self):
        base_url = 'plugin://plugin.video.kyivstar.tv/play/%s-%s|' % (self.id, self.type)
        groups = 'group-title="%s"' % ';'.join(self.groups)
        catchup = None
        if not self.catchup:
            catchup = ''
        elif self.type == 'VIRTUAL':
            catchup = 'catchup="vod" catchup-source="%s{catchup-id}"' % base_url
        else:
            catchup = 'catchup="default" catchup-source="%s{utc}"' % base_url
        text = '#EXTINF:0 tvg-id="%s" tvg-name="%s" tvg-logo="%s" %s %s,%s\n' % (self.id, self.name, self.logo, groups, catchup, self.name)

        if self.url == '':
            self.url = base_url + 'null'
        if not self.enabled:
            text += '#'
        text += self.url + '\n'

        return text

    def update(self, json):
        images = json.get('images', None)
        logo = images[0].get('url', None) if images and len(images) > 0 else None
        if logo:
            self.logo = logo

        name = json.get('displayName', None)
        if name is None:
            name = json.get('name', None)
        if name:
            self.name = name

        asset_id = json.get('assetId', None)
        if asset_id:
            self.id = asset_id

        ctype = json.get('type', None)
        ctype_value = ctype.get('value', None) if ctype else None
        if ctype_value:
            self.type = ctype_value

        self.groups = json.get('groups', '').split(';')

        self.catchup = json.get('catchupEnabled', None) == True

        self.url = 'plugin://plugin.video.kyivstar.tv/play/%s-%s|null' % (self.id, self.type)

class ChannelManager():
    def __init__(self):
        self.reset()

    def reset(self):
        self.all = {}
        self.enabled = []
        self.disabled = []
        self.new = []
        self.removed = []
        self.groups = []

    def to_dict(self):
        return {
            'enabled' : [channel.to_dict() for channel in self.enabled],
            'disabled' : [channel.to_dict() for channel in self.disabled],
            'new' : [channel.to_dict() for channel in self.new],
            'removed' : [channel.to_dict() for channel in self.removed],
            'groups' : self.groups
        }

    def load(self, file_path):
        with xbmcvfs.File(file_path) as f:
            lines = f.read().split('\n')

        groups = set()
        channel = Channel()
        for line in lines:
            if line == '' or line.startswith('#EXTM3U'):
                continue
            channel.read(line)
            if channel.url == '':
                continue
            if channel.enabled:
                self.enabled.append(channel)
            else:
                self.disabled.append(channel)
            self.all[channel.id] = channel
            groups.update(channel.groups)
            channel = Channel()
        self.groups = list(groups)

    def save(self, file_path):
        data = '#EXTM3U\n'
        for channel in self.enabled:
            data += channel.write()
        for channel in self.new:
            data += channel.write()
        for channel in self.disabled:
            data += channel.write()

        with xbmcvfs.File(file_path, 'w') as f:
            f.write(data.encode("utf-8"))

    def download(self, service):
        session_id = service.addon.getSetting('session_id')

        groups = service.request.get_live_channels_groups(session_id)

        if len(groups) == 0:
            return False

        all_channels = {}
        include_groups = service.addon.getSetting('m3u_include_kyivstar_groups') == 'true'
        include_favorites_group = service.addon.getSetting('m3u_include_favorites_group') == 'true'

        for group in groups:
            group_id = group.get('assetId', None)
            group_name = group.get('name', None)
            group_type = group.get('type', None) # ALL_CHANNELS, FAVORITES, REGULAR
            if group_id is None:
                continue
            if not include_groups and group_type != 'ALL_CHANNELS':
                continue
            if not include_favorites_group and group_type == 'FAVORITES':
                continue
            channels = service.request.get_group_elems(session_id, group_id)
            for channel in channels:
                if not channel.get('purchased', None):
                    continue
                asset_id = channel.get('assetId', None)
                if asset_id is None:
                    continue
                if asset_id not in all_channels:
                    all_channels[asset_id] = channel
                channel = all_channels[asset_id]
                if group_type == 'ALL_CHANNELS':
                    continue
                if 'groups' not in channel:
                    channel['groups'] = group_name
                else:
                    channel['groups'] += ';' + group_name
            time.sleep(0.1)

        if len(all_channels) == 0:
            return False

        for channel in all_channels.values():
            asset_id = channel.get('assetId', None)
            if asset_id in self.all:
                self.all[asset_id].update(channel)
            else:
                self.all[asset_id] = Channel()
                self.new.append(self.all[asset_id])
                self.all[asset_id].update(channel)

        for channel in self.all.values():
            if channel.id in all_channels:
                continue
            self.removed.append(channel)
            if channel.enabled:
                self.enabled.remove(channel)
            else:
                self.disabled.remove(channel)
        return True
