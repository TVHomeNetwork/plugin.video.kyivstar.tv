import bisect
import queue
import threading
import time

import xbmc

from collections import deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

class Stream():
    def __init__(self, url, playlist_url, bandwidth=None, resolution=None, stream_inf=None):
        self.playlist_url = playlist_url
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
        self.start_time = 0.0

        self.lock = threading.RLock()
        self.last_update = 0.0

        self.reset()

    def get_last_update(self):
        return self.last_update

    def set_last_update(self, cur_time):
        self.last_update = cur_time

    def reset(self):
        with self.lock:
            self.finished = False
            self.segments = []
            self.segments_start = []
            self.segments_end = []
            self.discont_indexes = []
            self.target_duration = 0

    def parse(self, text, base_url):
        lines = text.splitlines()

        finished = False
        segments = []
        segments_start = []
        segments_end = []
        discont_indexes = []
        target_duration = 0

        segment_tags = []
        segment_duration = 0.0
        segment_offset = 0.0
        segment_discontinuity = False
        for line in lines:
            if line.startswith('#EXT-X-TARGETDURATION:'):
                target_duration = int(line[22:])
            elif line == '#EXT-X-DISCONTINUITY':
                segment_tags.append(line)
                segment_discontinuity = True
                pass
            elif line == '#EXT-X-ENDLIST':
                finished = True
            elif line.startswith('https://adroll.production.vidmind.com'):
                segment_tags = []
                segment_discontinuity = False
            elif line.startswith('#EXTINF:'):
                segment_tags.append(line)
                segment_duration = float(line[8:len(line)-1])
            elif len(line) > 0 and not line.startswith('#'):
                if not line.startswith('https://'):
                    line = urljoin(base_url, line)
                if segment_discontinuity:
                    discont_indexes.append(len(segments))
                    segment_discontinuity = False
                segments.append({
                    'url' : line,
                    'tags' : segment_tags,
                })
                segments_start.append(segment_offset)
                segments_end.append(segment_offset + segment_duration)
                segment_tags = []
                segment_offset += segment_duration

        with self.lock:
            self.finished = finished
            self.segments = segments
            self.segments_start = segments_start
            self.segments_end = segments_end
            self.discont_indexes = discont_indexes
            self.target_duration = target_duration

    def get_discont_sequence(self, live, segment_index=None):
        with self.lock:
            if len(self.segments) == 0:
                return 0

            if segment_index is None:
                segment_index = len(self.segments)

            discont_count = 0
            if live and segment_index > 0:
                discont_count += 1
            for discont_index in self.discont_indexes:
                if segment_index <= discont_index:
                    break
                discont_count += 1

            return discont_count

    def set_start_time(self, cur_time):
        with self.lock:
            self.start_time = cur_time

    def get_segment_start_time(self, index):
        with self.lock:
            count = len(self.segments)
            if not (-count <= index < count):
                xbmc.log("KyivstarStreamManager Stream.get_segment_start_time: the index %s is out of range for the segments list with the length %s" % (index, count), xbmc.LOGERROR)
                return 0.0
            return self.segments_start[index] + self.start_time

    def get_segment_end_time(self, index):
        with self.lock:
            count = len(self.segments)
            if not (-count <= index < count):
                xbmc.log("KyivstarStreamManager Stream.get_segment_end_time: the index %s is out of range for the segments list with the length %s" % (index, count), xbmc.LOGERROR)
                return 0.0
            return self.segments_end[index] + self.start_time

    def get_start_time(self):
        with self.lock:
            if len(self.segments) == 0:
                return self.start_time
            return self.segments_start[0] + self.start_time

    def get_end_time(self):
        with self.lock:
            if len(self.segments) == 0:
                return self.start_time
            return self.segments_end[-1] + self.start_time

    def is_in_bound(self, cur_time):
        with self.lock:
            if len(self.segments) == 0:
                return False
            start_time = self.segments_start[0] + self.start_time
            end_time = self.segments_end[-1] + self.start_time
            return start_time <= cur_time < end_time

    def get_segment_index(self, cur_time):
        with self.lock:
            if len(self.segments) == 0:
                return 0
            cur_time -= self.start_time
            index = bisect.bisect(self.segments_start, cur_time) - 1
            return max(0, min(index, len(self.segments) - 1))

class ChannelState():
    def __init__(self, service, asset_id, virtual):
        self.service = service
        self.asset_id = asset_id
        self.virtual = virtual

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

        self.lock = threading.RLock()
        self.update_queue = queue.Queue()
        self.pending_updates = set()

        self.worker_thread = threading.Thread(target=self._update_worker)
        self.worker_thread.start()

    def _update_worker(self):
        while True:
            task = self.update_queue.get()

            if task is None:
                self.update_queue.task_done()
                break

            if not isinstance(task, dict):
                xbmc.log("KyivstarStreamManager _update_worker: received invalid task %s" % str(task), xbmc.LOGWARNING)
                self.update_queue.task_done()
                continue

            if task.get('action') == 'stop':
                self.update_queue.task_done()
                break

            if task.get('action') == 'update_stream':
                program_index = task.get('program_index')
                stream_id = task.get('stream_id')

                try:
                    retries = 2

                    for attempt in range(retries):
                        stream = self.get_stream(stream_id, program_index)

                        if stream is None:
                            xbmc.log("KyivstarStreamManager _update_worker: the stream with the id %s is not found for the program index %s of the asset %s" % (stream_id, program_index, self.asset_id), xbmc.LOGERROR)
                            break

                        result = self.service.request.send(stream.url, ret_json=False)
                        if not result.error:
                            stream.parse(result.value, result.url)
                            stream.set_last_update(time.time())
                            break
                        elif not result.recoverable and result.error.startswith('403'):
                            with self.lock:
                                del self.streams[program_index]
                            xbmc.log("KyivstarStreamManager _update_worker: 403 Forbidden for cached stream %s. Cleared cache." % str(program_index), xbmc.LOGWARNING)
                        else:
                            xbmc.log("KyivstarStreamManager _update_worker: error for asset %s: %s" % (self.asset_id, result.error), xbmc.LOGERROR)
                        xbmc.sleep(1)
                except Exception as e:
                    xbmc.log("KyivstarStreamManager _update_worker: stream update exception: %s" % str(e), xbmc.LOGERROR)
                finally:
                    with self.lock:
                        self.pending_updates.discard((program_index, stream_id))
                    self.update_queue.task_done()

            elif task.get('action') == 'prefetch_program':
                program_index = task.get('program_index')

                try:
                    with self.lock:
                        is_cached = program_index in self.streams
                    if not is_cached:
                        self.get_streams(program_index)
                except Exception as e:
                    xbmc.log("KyivstarStreamManager _update_worker: prefetch exception: %s" % str(e), xbmc.LOGERROR)
                finally:
                    self.update_queue.task_done()

    def stop(self):
        self.update_queue.put({ 'action': 'stop' })
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3.0)

    def get_stream_id(self, stream):
        stream_info = (stream.resolution, stream.bandwidth)
        with self.lock:
            stream_id = self.stream_infos.get(stream_info)
            if stream_id is not None:
                return stream_id

            stream_id = self.free_stream_id
            self.free_stream_id += 1
            self.stream_infos[stream_info] = stream_id
            self.stream_ids[stream_id] = {
                'resolution': stream_info[0],
                'bandwidth': stream_info[1],
                'alternates': []
            }

            for i in self.stream_ids:
                self.stream_ids[i]['alternates'] = []
                for j in self.stream_ids:
                    if j == i or j in self.stream_ids[i]['alternates']:
                        continue
                    if self.stream_ids[i]['resolution'] != self.stream_ids[j]['resolution']:
                        continue
                    self.stream_ids[i]['alternates'].append(j)
                for j in self.stream_ids:
                    if j == i or j in self.stream_ids[i]['alternates']:
                        continue
                    if self.stream_ids[i]['bandwidth'] != self.stream_ids[j]['bandwidth']:
                        continue
                    self.stream_ids[i]['alternates'].append(j)
                for j in self.stream_ids:
                    if j == i or j in self.stream_ids[i]['alternates']:
                        continue
                    self.stream_ids[i]['alternates'].append(j)

            return stream_id

    def get_program_list(self, date_index):
        with self.lock:
            if date_index in self.program_list:
                return self.program_list[date_index]

        session_id = self.service.addon.getSetting('session_id')
        result = self.service.request.get_elem_epg_data(session_id, self.asset_id, date=date_index, days_before=0, days_after=0)
        epg_data = result.value
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
        with self.lock:
            self.program_list[date_index] = program_list
        return program_list

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
        if program_index is None:
            return None
        date_index = program_index[0]
        index = program_index[1]
        program_list = self.get_program_list(date_index)
        if index >= len(program_list):
            return None
        return program_list[index]

    def get_streams(self, program_index, force=False):
        with self.lock:
            if program_index in self.streams and not force:
                return self.streams[program_index]

        program = self.get_program(program_index)
        epg = program['epg'] if program else None
        session_id = self.service.addon.getSetting('session_id')
        user_id = self.service.addon.getSetting('user_id')
        if not self.virtual and epg is not None:
            result = self.service.request.get_elem_playback_stream_url(user_id, session_id, self.asset_id, date=epg)
        else:
            result = self.service.request.get_elem_stream_url(user_id, session_id, self.asset_id, virtual=self.virtual, date=epg)
        if result.error and result.error.startswith('Pin code is required'):
            self.service.addon.setSetting('adult_content_enabled', 'true')
            return {}
        result = self.service.request.send(result.value, ret_json=False)
        text = result.value
        url = result.url
        if result.error or text is None:
            xbmc.log("KyivstarStreamManager get_streams: %s" % result.error, xbmc.LOGERROR)
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
                stream = Stream(line, url, stream_inf=stream_inf)
                stream_id = self.get_stream_id(stream)
                streams[stream_id] = stream
        with self.lock:
            self.streams[program_index] = streams
        return streams

    def get_stream(self, stream_id, program_index):
        streams = self.get_streams(program_index)
        if streams is None:
            return None

        if stream_id not in streams:
            if stream_id not in self.stream_ids:
                return None
            for i in self.stream_ids[stream_id]['alternates']:
                if i in streams:
                    stream_id = i
                    break
            if stream_id not in streams:
                xbmc.log("KyivstarStreamManager get_stream: streams for the %s program index doesn't contain an alternative stream for the %s id" % (program_index, stream_id), xbmc.LOGERROR)
                return None

        return streams[stream_id]

    def update_timeline(self, stream_id, live, start_date, end_date, window_end_date):
        with self.lock:
            program_index = self.program_index if live else None
            start_time = self.start_time if live else 0

        if start_date is not None and program_index is None:
            program_index = self.get_program_index(start_date)
            program = self.get_program(program_index)
            start_time = program['epg']/1000 if program else 0

        start_program_index = program_index
        need_start_time_correction = False

        if live:
            with self.lock:
                if self.start_time == 0:
                    self.start_time = start_time
                    need_start_time_correction = not self.virtual
                else:
                    start_time = self.start_time

        retried_programs = set()

        while True:
            stream = self.get_stream(stream_id, program_index)
            if stream is None:
                return None

            if not stream.finished:
                now = time.time()
                is_in_window = start_time < window_end_date.timestamp() if window_end_date else True
                if len(stream.segments) == 0 and is_in_window:
                    result = self.service.request.send(stream.url, ret_json=False)
                    if not result.error:
                        stream.parse(result.value, result.url)
                        stream.set_last_update(now)
                        if need_start_time_correction:
                            if len(stream.segments) > 0:
                                total_duration = stream.segments_end[-1]
                                real_start_time = now - total_duration

                                if real_start_time > start_date.timestamp():
                                    prev_program_index = self.get_prev_program_index(program_index)
                                    if prev_program_index is not None:
                                        program_index = prev_program_index
                                        start_program_index = prev_program_index
                                        with self.lock:
                                            self.program_index = prev_program_index

                                        prev_program = self.get_program(prev_program_index)
                                        prev_start_time = prev_program['epg']/1000 if prev_program else 0
                                        prev_real_start_time = prev_start_time + real_start_time - start_time
                                        
                                        start_time = prev_real_start_time
                                        with self.lock:
                                            self.start_time = start_time

                                        need_start_time_correction = False
                                        continue
                                else:
                                    start_time = real_start_time
                                    with self.lock:
                                        self.start_time = start_time
                            need_start_time_correction = False
                    elif not result.recoverable:
                        if result.error.startswith('403'):
                            xbmc.log("KyivstarStreamManager update_timeline: 403 Forbidden for cached stream %s. Cleared cache." % str(program_index), xbmc.LOGWARNING)
                            del self.streams[program_index]
                            if program_index not in retried_programs:
                                retried_programs.add(program_index)
                                continue
                        xbmc.log("KyivstarStreamManager update_timeline: %s" % result.error, xbmc.LOGERROR)
                        return None
                else:
                    last_update = stream.get_last_update()
                    with self.lock:
                        is_queued = (program_index, stream_id) in self.pending_updates
                    if not is_queued and (now - last_update >= stream.target_duration):
                        with self.lock:
                            self.pending_updates.add((program_index, stream_id))
                        self.update_queue.put({ 'action': 'update_stream', 'program_index': program_index, 'stream_id': stream_id})

            if stream.finished:
                prefetch_start_time = stream.get_end_time() - 2 * stream.target_duration
                can_prefetch = prefetch_start_time <= end_date.timestamp() if end_date else False
                if can_prefetch:
                    next_program_index = self.get_next_program_index(program_index)
                    if next_program_index is not None:
                        with self.lock:
                            is_cached = next_program_index in self.streams
                        if not is_cached:
                            self.update_queue.put({ 'action': 'prefetch_program', 'program_index': next_program_index})

            stream.set_start_time(start_time)

            if end_date is None:
                break

            if start_date is not None:
                with self.lock:
                    if self.program_index is None:
                        self.program_index = program_index
                    elif not stream.is_in_bound(start_date.timestamp()):
                        new_program_index = self.get_program_index(start_date)
                        next_program_index = self.get_next_program_index(program_index)
                        if new_program_index == program_index or new_program_index == next_program_index:
                            program_index = next_program_index
                            self.media_sequence += len(stream.segments)
                            self.discontinuity_sequence += stream.get_discont_sequence(live)
                            self.start_time = stream.get_end_time()
                        else:
                            program_index = new_program_index
                            self.media_sequence = 0
                            self.discontinuity_sequence = 0
                            program = self.get_program(program_index)
                            self.start_time = program['epg']/1000 if program else 0
                        self.program_index = program_index
                        start_program_index = program_index
                        start_time = self.start_time
                        start_date = None
                        continue

            if stream.is_in_bound(end_date.timestamp()) or not stream.finished:
                break

            program_index = self.get_next_program_index(program_index)
            if program_index is None:
                break

            start_time = stream.get_end_time()
            start_date = None
        return start_program_index

    def get_next_program_index(self, program_index):
        if program_index is None:
            return None
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

    def get_prev_program_index(self, program_index):
        if program_index is None:
            return None
        date_index = program_index[0]
        index = program_index[1] - 1

        if index >= 0:
            return (date_index, index)

        date_index -= timedelta(days=1)
        program_list = self.get_program_list(date_index)
        if len(program_list) > 0:
            return (date_index, len(program_list) - 1)

        return None

    def get_stream_segments(self, stream_id, program_index, live, start_date, end_date):
        with self.lock:
            media_sequence = self.media_sequence if live else 0
            start_time = self.start_time if live else 0

        while True:
            stream = self.get_stream(stream_id, program_index)
            if stream is None:
                break

            stream.set_start_time(start_time)
            switch_program = False
            start_index = 0
            end_index = len(stream.segments)
            if start_date is not None:
                if stream.is_in_bound(start_date.timestamp()):
                    start_index = stream.get_segment_index(start_date.timestamp())
                else:
                    program_index = self.get_next_program_index(program_index)
                    if program_index is None:
                        break

                    media_sequence += len(stream.segments)
                    start_time = stream.get_end_time()
                    continue
            if end_date is not None:
                if stream.is_in_bound(end_date.timestamp()):
                    end_index = stream.get_segment_index(end_date.timestamp())
                else:
                    switch_program = True

            if live and start_index == 0 and end_index > 0:
                yield -1, { "url" : None, "tags" : [ '#EXT-X-DISCONTINUITY' ] }, None

            for i in range(start_index, end_index):
                yield media_sequence + i, stream.segments[i], stream.get_segment_start_time(i)

            if not stream.finished or not switch_program or not live:
                break

            program_index = self.get_next_program_index(program_index)
            if program_index is None:
                break

            start_date = None
            media_sequence += len(stream.segments)
            start_time = stream.get_end_time()

class SegmentCacheManager():
    def __init__(self, service):
        self.service = service
        self.cache = {}
        self.queue = deque()
        self.queue_set = set()
        self.process_thread = None
        self.process_key = None
        self.queue_event = threading.Event()
        self.abort_event = threading.Event()
        self.lock = threading.Lock()

    def process(self):
        wait_time = None
        while not self.abort_event.is_set():
            self.queue_event.wait(timeout=wait_time)
            self.queue_event.clear()

            with self.lock:
                if len(self.queue) == 0:
                    wait_time = None
                    continue
                key = self.queue.popleft()
                self.queue_set.discard(key)
                cache_entry = self.cache.get(key)
                if not cache_entry:
                    wait_time = 0
                    continue
                if cache_entry["content"]:
                    cache_entry["waiter"].set()
                    wait_time = 0
                    continue
                self.process_key = key
                url = cache_entry["url"]

            result = self.service.request.send(url, ret_json=False, ret_binary=True)
            content = result.value
            if result.error:
                xbmc.log("KyivstarStreamManager SegmentCacheManager.process: %s" % result.error, xbmc.LOGERROR)
                content = None
            if result.error and wait_time is not None:
                wait_time = min(wait_time + 0.5, 10)
            else:
                wait_time = 0.5

            event = None
            with self.lock:
                self.process_key = None
                cache_entry = self.cache.get(key)
                if not cache_entry:
                    continue
                cache_entry["content"] = content
                cache_entry["waiter"].set()

    def start(self):
        if self.process_thread is not None:
            return
        self.abort_event.clear()
        self.process_thread = threading.Thread(target=self.process)
        self.process_thread.start()

    def stop(self):
        if self.process_thread is None:
            return
        self.abort_event.set()
        self.queue_event.set()
        self.process_thread.join()
        self.process_thread = None
        self.clear()

    def get(self, asset_id, segment_id):
        key = (asset_id, segment_id)
        with self.lock:
            cache_entry = self.cache.get(key)
            if not cache_entry:
                return None

            content = cache_entry["content"]
            if content:
                return content

            self.queue.appendleft(key)
            self.queue_set.add(key)
            event = cache_entry["waiter"]

        if not event.wait(5):
            xbmc.log("KyivstarStreamManager SegmentCacheManager.get: timeout while waiting for the segment content for the key %s" % str(key), xbmc.LOGERROR)
            return None

        with self.lock:
            cache_entry = self.cache.get(key)
            if not cache_entry:
                xbmc.log("KyivstarStreamManager SegmentCacheManager.get: the key %s is not in cache after waiting for the content" % str(key), xbmc.LOGERROR)
                return None
            return cache_entry["content"]

    def update(self, asset_id, cache_list):
        with self.lock:
            valid_keys = set()
            for segment_id, url in cache_list:
                key = (asset_id, segment_id)
                valid_keys.add(key)
                cache_entry = self.cache.get(key)
                if not cache_entry:
                    cache_entry = {
                        "content" : None,
                        "waiter" : threading.Event()
                    }
                    self.cache[key] = cache_entry
                if cache_entry["content"] is None:
                    cache_entry["url"] = url
                    if key != self.process_key and key not in self.queue_set:
                        self.queue_set.add(key)
                        self.queue.append(key)

            if len(cache_list) > 0:
                for key in list(self.cache.keys()):
                    if key in valid_keys or key == self.process_key:
                        continue
                    del self.cache[key]
                    self.queue_set.discard(key)

            queue_size = len(self.queue)
            cache_size = len(self.cache)
            xbmc.log("KyivstarStreamManager SegmentCacheManager.update: queue_size=%s cache_size=%s" % (queue_size, cache_size), xbmc.LOGDEBUG)
        self.queue_event.set()
        return queue_size, cache_size

    def clear(self):
        with self.lock:
            self.cache = {}
            self.queue.clear()
            self.queue_set.clear()
            self.process_key = None

class KyivstarStreamManager():
    def __init__(self, server):
        self.server = server
        self.service = server.service
        self.channel_states = {}
        self.window_length = 60
        self.segment_cache = SegmentCacheManager(self.service)
        self.segment_cache.start()
        self.lock = threading.RLock()

    def check_active_states(self):
        outdated_states = []
        time_limit = datetime.now() - timedelta(minutes=30)
        with self.lock:
            for asset_id in self.channel_states:
                channel_state = self.channel_states[asset_id]
                if channel_state.last_access_time < time_limit:
                    outdated_states.append(asset_id)

            for asset_id in outdated_states:
                self.channel_states[asset_id].stop()
                del self.channel_states[asset_id]
        xbmc.log("KyivstarStreamManager check_active_states: active=%s outdated=%s" % (len(self.channel_states), len(outdated_states)), xbmc.LOGDEBUG)

    def stop(self):
        with self.lock:
            for asset_id in list(self.channel_states.keys()):
                self.channel_states[asset_id].stop()
            self.channel_states.clear()

        self.segment_cache.stop()

    def get_playlist_content(self, asset_id, virtual, epg):
        if epg is None:
            date = datetime.now()
        elif epg < 0:
            date = None
        else:
            date = datetime.fromtimestamp(epg/1000)

        with self.lock:
            if self.service.drop_channel_states:
                self.service.drop_channel_states = False
                for asset_id in list(self.channel_states.keys()):
                    self.channel_states[asset_id].stop()
                self.channel_states.clear()

            if asset_id not in self.channel_states:
                self.channel_states[asset_id] = ChannelState(self.service, asset_id, virtual)
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

        with self.lock:
            channel_state = self.channel_states.get(asset_id)
        if channel_state is None:
            xbmc.log("KyivstarStreamManager get_chunklist_content: the asset %s has no channel state" % asset_id, xbmc.LOGERROR)
            return None
        channel_state.last_access_time = datetime.now()

        cache_size = int(self.service.addon.getSetting('segment_cache_size'))
        cache_enabled = True
        if channel_state.virtual:
            cache_enabled = self.service.addon.getSetting('segment_cache_virtual_enabled') == 'true'
        elif live:
            date = date - timedelta(seconds=cache_size)

        start_date = None
        end_date = None
        if live:
            start_date = date - timedelta(seconds=self.window_length)
            end_date = date
        else:
            start_date = date

        cache_end_date = end_date
        if cache_end_date is not None:
            if cache_enabled:
                cache_end_date += timedelta(seconds=cache_size)
            else:
                cache_end_date += timedelta(seconds=60)

        program_index = channel_state.update_timeline(stream_id, live, start_date, cache_end_date, end_date)
        if program_index is None and date is not None:
            return None

        stream = channel_state.get_stream(stream_id, program_index)
        if stream is None:
            return None

        start_index = 0
        if live:
            start_index = stream.get_segment_index(start_date.timestamp())
        else:
            start_date = None

        text = "#EXTM3U\n#EXT-X-VERSION:3\n"
        text += "#EXT-X-TARGETDURATION:%s\n" % stream.target_duration
        media_sequence = channel_state.media_sequence + start_index
        text += "#EXT-X-MEDIA-SEQUENCE:%s\n" % media_sequence
        discontinuity_sequence = channel_state.discontinuity_sequence + stream.get_discont_sequence(live, start_index)
        text += "#EXT-X-DISCONTINUITY-SEQUENCE:%s\n\n" % discontinuity_sequence

        base_url = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}/segment.ts"
        base_url += f"?asset={asset_id}&stream={stream_id}{'' if epg is None else '&epg=' + str(epg)}&segment="

        for segment_id, segment, start_time in channel_state.get_stream_segments(stream_id, program_index, live, start_date, end_date):
            #if live and start_time:
            #    text += '#EXT-X-PROGRAM-DATE-TIME:%s\n' % datetime.fromtimestamp(start_time, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            for tag in segment['tags']:
                text += tag + '\n'
            if not segment["url"]:
                continue
            if cache_enabled:
                text += base_url + str(start_time) + '\n'
            else:
                text += segment['url'] + '\n'

        if not live:
            text += '#EXT-X-ENDLIST\n'

        return text

    def get_segment_content(self, asset_id, stream_id, segment_id, epg):
        live = False
        if epg is None:
            date = datetime.now()
            live = True
        elif epg < 0:
            date = None
        else:
            date = datetime.fromtimestamp(epg/1000)

        with self.lock:
            channel_state = self.channel_states.get(asset_id)
        if channel_state is None:
            xbmc.log("KyivstarStreamManager get_segment_content: the asset %s has no channel state" % asset_id, xbmc.LOGERROR)
            return None
        channel_state.last_access_time = datetime.now()

        if live:
            program_index = channel_state.program_index
        else:
            program_index = channel_state.get_program_index(date)
        if program_index is None and date is not None:
            return None

        stream = channel_state.get_stream(stream_id, program_index)
        if stream is None:
            return None

        cache_size_setting = int(self.service.addon.getSetting('segment_cache_size'))
        start_date = datetime.fromtimestamp(segment_id)
        end_date = start_date + timedelta(seconds=cache_size_setting)

        cache_list = [ (start_time, segment["url"]) for _, segment, start_time in channel_state.get_stream_segments(stream_id, program_index, live, start_date, end_date) if segment["url"]]

        queue_size, cache_size = self.segment_cache.update(asset_id, cache_list)
        if stream.target_duration > 0:
            calc_cache_size = cache_size_setting // stream.target_duration
            if calc_cache_size > cache_size:
                queue_size += calc_cache_size - cache_size
                cache_size = calc_cache_size
        self.service.update_cache_overlay(queue_size, cache_size)

        return self.segment_cache.get(asset_id, segment_id)
