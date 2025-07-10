import requests
import time

import xbmc

from urllib.parse import urljoin

class KyivstarStreamManager(object):
    def __init__(self, server, asset_id, epg):
        self.server = server
        self.asset_id = asset_id
        self.epg = epg
        self.service = server.service

        self.headers = {
            'User-Agent': self.service.request.headers['User-Agent'],
            'Referer': self.service.request.headers['Referer'],
            'Origin': self.service.request.headers['Origin'],
            }
        self.hls = {}
        self.program_list = []
        self.program_index = -1
        self.active_chunk_time = -1

    def download(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarStreamManager exception on loading %s: %s" % (url, str(e)), xbmc.LOGERROR)
            return None

    def parse_playlist(self, text, playlist_url):
        server_address = self.server.server_address
        live = 'live&'
        if self.epg:
            live = ''
        base_url = "http://%s:%s/chunklist.m3u8?%surl={}" % (server_address[0], server_address[1], live)
        hls = {}
        bandwidth = -1
        resolution = ''
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF:'):
                for pair in line[18:].split(','):
                    if pair.startswith('BANDWIDTH'):
                        bandwidth = int(pair.split('=')[1])
                    elif pair.startswith('RESOLUTION'):
                        resolution = pair.split('=')[1]
            if not line.startswith('#'):
                if not line.startswith('https://'):
                    line = urljoin(playlist_url, line)
                lines[index] = base_url.format(line)
                hls[line] = {
                    'url' : line,
                    'bandwidth' : bandwidth,
                    'resolution' : resolution,
                    }
                bandwidth = -1
                resolution = ''
        text = ('\n'.join(lines)+'\n')
        return hls, text

    def get_playlist_content(self):
        service = self.service
        asset_id = self.asset_id
        session_id = service.addon.getSetting('session_id')
        user_id = service.addon.getSetting('user_id')

        stream_url = service.request.get_elem_stream_url(user_id, session_id, asset_id, virtual=True, date=self.epg)
        if stream_url == '':
            return None

        response = self.download(stream_url)
        if not response:
            return None
        text = response.text
        playlist_url = stream_url
        if len(response.history) > 0:
            playlist_url = response.history[0].headers['Location']

        self.hls, text = self.parse_playlist(text, playlist_url)
        content = text.encode('utf-8')

        if self.epg:
            return content

        epg_data = service.request.get_elem_epg_data(session_id, asset_id, days_before=0, days_after=1)
        if len(epg_data) != 2: 
            xbmc.log("KyivstarStreamManager: can't load epg data", xbmc.LOGERROR)
            return content

        for epg_day_data in epg_data:
            if 'programList' not in epg_day_data:
                continue
            self.program_list.extend(epg_day_data['programList'])

        cur_time = int(time.time() * 1000)
        for index, program in enumerate(self.program_list):
            if cur_time > int(program['start']) and cur_time < int(program['finish']):
                self.program_index = index
                break

        if self.program_index < 0:
            xbmc.log("KyivstarStreamManager: can't get current programme index", xbmc.LOGERROR)

        return content

    def get_program_chunklist(self, stream_data, next_program=False):
        stream_url = stream_data['url']
        if next_program:
            stream_data['prev-chunks'] = stream_data['chunks']

            service = self.service
            asset_id = self.asset_id

            session_id = service.addon.getSetting('session_id')
            user_id = service.addon.getSetting('user_id')

            self.program_index += 1

            date = self.program_list[self.program_index]['start']

            playlist_url = self.service.request.get_elem_stream_url(user_id, session_id, asset_id, virtual=True, date=date)
            if playlist_url != '':
                response = self.download(playlist_url)
                if response:
                    if len(response.history) > 0:
                        playlist_url = response.history[0].headers['Location']
                    hls, _ = self.parse_playlist(response.text, playlist_url)
                    new_stream_url = None
                    for url in hls:
                        if hls[url]['resolution'] == stream_data['resolution']:
                            new_stream_url = url
                            break;
                    if not new_stream_url:
                        for url in hls:
                            if hls[url]['bandwidth'] == stream_data['bandwidth']:
                                new_stream_url = url
                                break;
                    if not new_stream_url:
                        for url in hls:
                            new_stream_url = url
                            break;
                    stream_url = new_stream_url

        if not stream_url:
            stream_data['chunks'] = []
            return

        response = self.download(stream_url)
        if not response:
            stream_data['chunks'] = []
            return

        lines = response.text.splitlines()
        chunks = []
        chunk_options = []

        chunk_start = 0.0
        if next_program:
            if len(stream_data['prev-chunks']) > 0:
                chunk_start = stream_data['prev-chunks'][-1]['end']
            else:
                chunk_start = time.time()
        elif self.program_index < 0:
            chunk_start = time.time()
        else:
            chunk_start = float(self.program_list[self.program_index]['start']) / 1000

        chunk_duration = 0.0
        for line in lines:
            if line == '':
                pass
            elif line.startswith('#EXT-X-DISCONTINUITY-SEQUENCE:'):
                pass
            elif line.startswith('#EXT-X-TARGETDURATION:'):
                stream_data['target-duration'] = int(line[22:])
            elif line.startswith('#EXT-X-DISCONTINUITY'):
                pass
            elif line.startswith('#EXTINF:'):
                chunk_options.append(line)
                chunk_duration = float(line[8:len(line)-1])
            elif line.startswith('https://adroll.production.vidmind.com'):
                chunk_options = []
            elif not line.startswith('#'):
                if not line.startswith('https://'):
                    line = urljoin(stream_url, line)
                chunks.append({
                    'url' : line,
                    'options' : chunk_options,
                    'start' : chunk_start,
                    'end' : chunk_start + chunk_duration,
                    })
                chunk_options = []
                chunk_start += chunk_duration

        #if len(chunks) > 0:
        #    chunks[0]['options'].append('#EXT-X-DISCONTINUITY')

        program_length = 0
        if self.program_index >= 0:
            program = self.program_list[self.program_index]
            program_length = int((program['finish'] - program['start'])/1000)
        stream_length = 0
        if len(chunks) > 0:
            stream_length = int(chunks[-1]['end'] - chunks[0]['start'])
        xbmc.log("KyivstarStreamManager: program_length = %s, stream_length = %s" % (program_length, stream_length), xbmc.LOGDEBUG)

        stream_data['chunks'] = chunks

    def get_current_chunk_index(self, chunks):
        index = len(chunks)
        cur_time = time.time()
        for i, chunk in enumerate(chunks):
            if cur_time >= chunk['start'] and cur_time <= chunk['end']:
                index = i
                break
        return index

    def get_chunklist_content(self, stream_url, live):
        stream_data = self.hls[stream_url]

        if 'chunks' not in stream_data:
            self.get_program_chunklist(stream_data)
            stream_data['sequence'] = 0
            stream_data['discontinuity-sequence'] = 0

        chunks = stream_data['chunks']
        index = self.get_current_chunk_index(chunks)

        shift = 0
        if 'index' in stream_data:
            shift += index - stream_data['index']

        if index >= len(chunks):
            if self.program_index >= 0 and (self.program_index + 1) < len(self.program_list):
                self.get_program_chunklist(stream_data, next_program=True)
                chunks = stream_data['chunks']
                index = self.get_current_chunk_index(chunks)
                stream_data['index'] = 0
                shift += index - stream_data['index']

        stream_data['sequence'] += shift
        stream_data['index'] = index

        #discontinuity_count = 0
        #if index < 20 and 'prev-chunks' in stream_data:
        #    discontinuity_count = 1
        #if 'discontinuity-count' in stream_data and stream_data['discontinuity-count'] > discontinuity_count:
        #    stream_data['discontinuity-sequence'] += 1
        #stream_data['discontinuity-count'] = discontinuity_count

        if index < 20 and 'prev-chunks' not in stream_data:
            stream_data['sequence'] = 0

        xbmc.log("KyivstarStreamManager: stream_data (res:%s) index=%s(%s), sequence=%s, discontinuity-sequence=%s" % (stream_data['resolution'],
            stream_data['index'], len(stream_data['chunks']), stream_data['sequence'], stream_data['discontinuity-sequence']), xbmc.LOGDEBUG)

        chunklist = "#EXTM3U\n#EXT-X-VERSION:3\n"
        chunklist += "#EXT-X-TARGETDURATION:%s\n" % stream_data['target-duration']
        chunklist += "#EXT-X-MEDIA-SEQUENCE:%s\n" % stream_data['sequence']
        chunklist += "#EXT-X-DISCONTINUITY-SEQUENCE:%s\n\n" % stream_data['discontinuity-sequence']

        if index >= len(chunks):
            chunklist += '#EXT-X-ENDLIST\n'
        else:
            start = index - 20
            end = index + 1

            if not live:
                start = 0
                end = len(chunks)

            if start < 0:
                if 'prev-chunks' in stream_data:
                    prev_end = len(stream_data['prev-chunks'])
                    prev_start = prev_end + start
                    for i in range(prev_start, prev_end):
                        chunk = stream_data['prev-chunks'][i]
                        chunklist += '#EXT-X-PROGRAM-DATE-TIME:%s\n' % time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(chunk['start']))
                        for option in chunk['options']:
                            chunklist += option + '\n'
                        chunklist += chunk['url'] + '\n'
                else:
                    start = 0
            for i in range(start, end):
                chunk = chunks[i]
                if live:
                    chunklist += '#EXT-X-PROGRAM-DATE-TIME:%s\n' % time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(chunk['start']))
                for option in chunk['options']:
                    chunklist += option + '\n'
                chunklist += chunk['url'] + '\n'
                #xbmc.log("KyivstarStreamManager: stream_data chunk url=%s" % (chunk['url']), xbmc.LOGDEBUG)
            if not live:
                chunklist += '#EXT-X-ENDLIST\n'

        return chunklist.encode('utf-8')
