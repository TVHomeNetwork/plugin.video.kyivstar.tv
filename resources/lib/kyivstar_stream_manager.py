import xbmc

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

class Stream():
    def __init__(self, url, bandwidth=None, resolution=None, stream_inf=None):
        if stream_inf is not None:
            for pair in stream_inf[18:].split(','):
                if pair.startswith('BANDWIDTH'):
                    bandwidth = pair.split('=')[1]
                elif pair.startswith('RESOLUTION'):
                    resolution = pair.split('=')[1]
        self.stream_inf = stream_inf
        self.url = url
        self.bandwidth = bandwidth
        self.resolution = resolution

        self.segments = []
        self.discont_indexes = []
        self.target_duration = 0
        self.start_time = 0.0

    def parse(self, text, base_url):
        lines = text.splitlines()

        self.segments = []
        segment_tags = []
        segment_duration = 0.0
        segment_offset = 0.0
        for line in lines:
            if line.startswith('#EXT-X-TARGETDURATION:'):
                self.target_duration = int(line[22:])
            elif line == '#EXT-X-DISCONTINUITY':
                #segment_tags.append(line)
                #self.discont_indexes.append(len(self.segments))
                pass
            elif line.startswith('https://adroll.production.vidmind.com'):
                segment_tags = []
            elif line.startswith('#EXTINF:'):
                segment_tags.append(line)
                segment_duration = float(line[8:len(line)-1])
            elif len(line) > 0 and not line.startswith('#'):
                if not line.startswith('https://'):
                    line = urljoin(base_url, line)
                self.segments.append({
                    'url' : line,
                    'tags' : segment_tags,
                    'start' : segment_offset,
                    'end' : segment_offset + segment_duration,
                    })
                segment_tags = []
                segment_offset += segment_duration

    def get_discont_sequence(self, segment_index=None):
        if len(self.segments) == 0:
            return 0

        if segment_index is None:
            segment_index = len(self.segments)

        discont_count = 0
        for discont_index in self.discont_indexes:
            if segment_index < discont_index:
                break
            discont_count += 1

        return discont_count

    def set_start_time(self, cur_time):
        self.start_time = cur_time

    def get_segment_start_time(self, index):
        return self.segments[index]['start'] + self.start_time

    def get_segment_end_time(self, index):
        return self.segments[index]['end'] + self.start_time

    def get_start_time(self):
        return self.get_segment_start_time(0)

    def get_end_time(self):
        return self.get_segment_end_time(-1)

    def is_in_bound(self, cur_time):
        return cur_time >= self.get_start_time() and cur_time <= self.get_end_time()

    def get_segment_index(self, cur_time):
        if len(self.segments) == 0:
            return 0
        index = int((cur_time - self.get_start_time()) / self.target_duration)
        if index >= len(self.segments):
            index = len(self.segments) - 1
        if cur_time < self.get_segment_start_time(index):
            for i in range(index, -1, -1):
                if cur_time >= self.get_segment_start_time(i):
                    return i
        elif cur_time > self.get_segment_end_time(index):
            for i in range(index, len(self.segments)):
                if cur_time <= self.get_segment_end_time(i):
                    return i
        return index

class ChannelState():
    def __init__(self, service, asset_id):
        self.service = service
        self.asset_id = asset_id

        self.last_access_time = datetime.now()

        self.program_list = {}
        self.program_index = None

        self.streams = {}
        self.media_sequence = 0
        self.discontinuity_sequence = 0
        self.start_time = 0

        self.stream_infos = {}
        self.stream_ids = {}
        self.free_stream_id = 0

    def get_stream_id(self, stream):
        stream_info = (stream.resolution, stream.bandwidth)
        stream_id = self.stream_infos.get(stream_info)
        if stream_id is not None:
            return stream_id

        self.stream_infos[stream_info] = self.free_stream_id
        self.stream_ids[self.free_stream_id] = { 'resolution' : stream_info[0], 'bandwidth' : stream_info[1], 'alternates' : [] }
        self.free_stream_id += 1

        for i in self.stream_ids:
            self.stream_ids[i]['alternates'] = []
            for j in self.stream_ids:
                if j == i or j in self.stream_ids[i]['alternates']: continue
                if self.stream_ids[i]['resolution'] != self.stream_ids[j]['resolution']: continue
                self.stream_ids[i]['alternates'].append(j)
            for j in self.stream_ids:
                if j == i or j in self.stream_ids[i]['alternates']: continue
                if self.stream_ids[i]['bandwidth'] != self.stream_ids[j]['bandwidth']: continue
                self.stream_ids[i]['alternates'].append(j)
            for j in self.stream_ids:
                if j == i or j in self.stream_ids[i]['alternates']: continue
                self.stream_ids[i]['alternates'].append(j)
        return self.stream_infos[stream_info]

    def get_program_list(self, date_index):
        if date_index in self.program_list:
            return self.program_list[date_index]

        session_id = self.service.addon.getSetting('session_id')
        epg_data = self.service.request.get_elem_epg_data(session_id, self.asset_id, date=date_index, days_before=0, days_after=0)
        if len(epg_data) == 0:
            xbmc.log("KyivstarStreamManager get_program_list: can't load epg data", xbmc.LOGERROR)
            return []

        program_list = []
        for program in epg_data[0].get('programList', []):
            program_list.append({
                'epg' : program['start'],
                'start' : datetime.fromtimestamp(program['start']/1000),
                'end' : datetime.fromtimestamp(program['finish']/1000),
            })
        self.program_list[date_index] = program_list
        return self.program_list[date_index]

    def get_program_index(self, date):
        if date is None:
            return None

        date_index = date.replace(hour=0, minute=0, second=0, microsecond=0)
        program_list = self.get_program_list(date_index)
        if len(program_list) == 0:
            xbmc.log("KyivstarStreamManager get_program_index: program list is empty for the date=%s" % date, xbmc.LOGERROR)
            return None

        if date < program_list[0]['start']:
            date_index -= timedelta(days=1)
            program_list = self.get_program_list(date_index)
        elif date >= program_list[-1]['end']:
            date_index += timedelta(days=1)
            program_list = self.get_program_list(date_index)

        for index, program in enumerate(program_list):
            if date >= program['start'] and date < program['end']:
                return (date_index, index)

        xbmc.log("KyivstarStreamManager get_program_index: can't find the appropriate program index for the date=%s" % date, xbmc.LOGERROR)
        return None

    def get_program(self, program_index):
        date_index = program_index[0]
        index = program_index[1]
        program_list = self.get_program_list(date_index)
        if index >= len(program_list):
            return None
        return program_list[index]

    def get_streams(self, program_index):
        if program_index in self.streams:
            return self.streams[program_index]

        epg = self.get_program(program_index)['epg'] if program_index is not None else None
        session_id = self.service.addon.getSetting('session_id')
        user_id = self.service.addon.getSetting('user_id')
        url = self.service.request.get_elem_stream_url(user_id, session_id, self.asset_id, virtual=True, date=epg)
        text = self.service.request.send(url, ret_json=False)
        url = self.service.request.url
        if text is None:
            return None

        streams = {}
        stream_inf = None
        lines = text.splitlines()
        for line in lines:
            if line.startswith('#EXT-X-STREAM-INF:'):
                stream_inf = line
            elif len(line) > 0 and not line.startswith('#'):
                if not line.startswith('https://'):
                    line = urljoin(url, line)
                stream = Stream(line, stream_inf=stream_inf)
                stream_id = self.get_stream_id(stream)
                streams[stream_id] = stream
        self.streams[program_index] = streams
        return streams

    def get_stream(self, stream_id, program_index):
        streams = self.get_streams(program_index)
        if streams is None:
            return None

        if stream_id not in streams:
            for i in self.stream_ids[stream_id]['alternates']:
                if i in streams:
                    stream_id = i
                    break
            if stream_id not in streams:
                xbmc.log("KyivstarStreamManager get_stream: streams for the %s program index doesn't contain an alternative stream for the %s id" % (program_index, stream_id), xbmc.LOGERROR)
                return None

        stream = streams[stream_id]
        if len(stream.segments) == 0:
            text = self.service.request.send(stream.url, ret_json=False)
            if text is None:
                return None
            stream.parse(text, self.service.request.url)
            stream.set_start_time(self.start_time)

        return stream

    def get_next_program_index(self, program_index):
        date_index = program_index[0]
        index = program_index[1] + 1

        program_list = self.get_program_list(date_index)
        if index < len(program_list):
            return (date_index, index)

        date_index += timedelta(days=1)
        index = 0

        program_list = self.get_program_list(date_index)
        if index < len(program_list):
            return (date_index, index)

        return None

class KyivstarStreamManager():
    def __init__(self, server):
        self.server = server
        self.service = server.service
        self.channel_states = {}
        self.window_length = 10

    def check_active_states(self):
        outdated_states = []
        time_limit = datetime.now() - timedelta(minutes=30)
        for asset_id in self.channel_states:
            channel_state = self.channel_states[asset_id]
            if channel_state.last_access_time < time_limit:
                outdated_states.append(asset_id)

        for asset_id in outdated_states:
            del self.channel_states[asset_id]
        xbmc.log("KyivstarStreamManager check_active_states: active=%s outdated=%s" % (len(self.channel_states), len(outdated_states)), xbmc.LOGDEBUG)

    def get_playlist_content(self, asset_id, epg):
        if epg is None:
            date = datetime.now()
        elif epg < 0:
            date = None
        else:
            date = datetime.fromtimestamp(epg/1000)

        if asset_id not in self.channel_states:
            self.channel_states[asset_id] = ChannelState(self.service, asset_id)
        channel_state = self.channel_states[asset_id]
        channel_state.last_access_time = datetime.now()
        self.check_active_states()

        program_index = channel_state.get_program_index(date)
        if program_index is None and date is not None:
            return None

        streams = channel_state.get_streams(program_index)
        if streams is None:
            return None

        server_address = self.server.server_address
        base_url = f"http://{server_address[0]}:{server_address[1]}/chunklist.m3u8"
        base_url += f"?asset={asset_id}{'' if epg is None else '&epg=' + str(epg)}&stream="
        text = "#EXTM3U\n#EXT-X-VERSION:3\n"
        for i in streams:
            text += streams[i].stream_inf + "\n"
            text += base_url + str(i) + "\n"
        return text

    def get_chunklist_content(self, asset_id, stream_id, epg=None):
        live = False
        if epg is None:
            date = datetime.now()
            live = True
        elif epg < 0:
            date = None
        else:
            date = datetime.fromtimestamp(epg/1000)

        channel_state = self.channel_states.get(asset_id)
        if channel_state is None:
            xbmc.log("KyivstarStreamManager get_chunklist_content: the asset %s has no channel state" % asset_id, xbmc.LOGERROR)
            return None
        channel_state.last_access_time = datetime.now()

        if live:
            if channel_state.program_index is not None:
                program_index = channel_state.program_index
            else:
                program_index = channel_state.get_program_index(date)
                channel_state.start_time = channel_state.get_program(program_index)['epg']/1000
        else:
            program_index = channel_state.get_program_index(date)
        if program_index is None and date is not None:
            return None

        stream = channel_state.get_stream(stream_id, program_index)
        if stream is None:
            return None

        if live:
            if channel_state.program_index is None:
                channel_state.program_index = program_index
            elif not stream.is_in_bound(date.timestamp()):
                channel_state.start_time = stream.get_end_time()

                new_program_index = channel_state.get_program_index(date)
                next_program_index = channel_state.get_next_program_index(program_index)
                if new_program_index == program_index or new_program_index == next_program_index:
                    program_index = next_program_index
                    channel_state.media_sequence += len(stream.segments)
                    channel_state.discontinuity_sequence += stream.get_discont_sequence() + 1
                else:
                    program_index = new_program_index
                    channel_state.media_sequence = 0
                    channel_state.discontinuity_sequence = 0
                channel_state.program_index = program_index

                stream = channel_state.get_stream(stream_id, program_index)
                if stream is None:
                    return None

        start_index = 0
        end_index = len(stream.segments)
        if live:
            start_index = stream.get_segment_index(date.timestamp())
            end_index = min(start_index + self.window_length, len(stream.segments))

        text = "#EXTM3U\n#EXT-X-VERSION:3\n"
        text += "#EXT-X-TARGETDURATION:%s\n" % stream.target_duration
        media_sequence = channel_state.media_sequence + start_index
        text += "#EXT-X-MEDIA-SEQUENCE:%s\n" % media_sequence
        discontinuity_sequence = channel_state.discontinuity_sequence + stream.get_discont_sequence(start_index) + live
        text += "#EXT-X-DISCONTINUITY-SEQUENCE:%s\n\n" % discontinuity_sequence

        for i in range(start_index, end_index):
            segment = stream.segments[i]
            if live:
                text += '#EXT-X-PROGRAM-DATE-TIME:%s\n' % datetime.fromtimestamp(stream.get_segment_start_time(i), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            for tag in segment['tags']:
                text += tag + '\n'
            text += segment['url'] + '\n'

        if not live or start_index >= len(stream.segments):
            text += '#EXT-X-ENDLIST\n'
            return text

        if start_index + self.window_length == end_index:
            return text

        window_length = start_index + self.window_length - end_index
        start_time = stream.get_end_time()
        program_index = channel_state.get_next_program_index(program_index)

        stream = channel_state.get_stream(stream_id, program_index)
        if stream is None:
            return None

        stream.set_start_time(start_time)

        start_index = 0
        end_index = min(start_index + window_length, len(stream.segments))

        for i in range(start_index, end_index):
            segment = stream.segments[i]
            if i == start_index:
                text += '#EXT-X-DISCONTINUITY\n'
            text += '#EXT-X-PROGRAM-DATE-TIME:%s\n' % datetime.fromtimestamp(stream.get_segment_start_time(i), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            for tag in segment['tags']:
                text += tag + '\n'
            text += segment['url'] + '\n'

        return text
