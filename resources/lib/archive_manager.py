import json
import os
import datetime
import time
import sqlite3

import xbmc

from resources.lib.common import strip_html, SessionStatus

class ArchiveManager():
    def __init__(self):
        self.conn = None
        self.program_ids = None
        self.channel_ids = None
        self.cached_genres = {}

    def open(self, path):
        self.conn = sqlite3.connect(os.path.join(path, 'archive.db'), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                asset_id TEXT UNIQUE,
                type TEXT,
                updateDate INTEGER DEFAULT (CAST(strftime('%s','now', '-2 days') AS INTEGER))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                image_id INTEGER PRIMARY KEY,
                url TEXT UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS programs (
                program_id INTEGER PRIMARY KEY,
                asset_id TEXT UNIQUE,
                type TEXT,
                channel_id INTEGER,
                start INTEGER,
                parse_step INTEGER,
                release_date INTEGER,
                duration INTERGER,
                image_id INTEGER,
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
                FOREIGN KEY (image_id) REFERENCES images (image_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS texts (
                text_id INTEGER PRIMARY KEY,
                value TEXT UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS program_texts (
                program_id INTEGER,
                locale VARCHAR(5),
                is_name BOOLEAN,
                text_id INTEGER,
                FOREIGN KEY (text_id) REFERENCES texts (text_id),
                FOREIGN KEY (program_id) REFERENCES programs (program_id),
                PRIMARY KEY (program_id, locale, is_name)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genres (
                genre_id INTEGER PRIMARY KEY,
                name TEXT UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS program_genres (
                program_id INTEGER,
                genre_id INTEGER,
                FOREIGN KEY (program_id) REFERENCES programs (program_id),
                FOREIGN KEY (genre_id) REFERENCES genres (genre_id)
            )
        ''')
        self.conn.commit()
        cursor.close()

    def enable_channel(self, channel):
        conn = self.conn
        if conn is None:
            return

        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO channels (asset_id, type) VALUES (?, ?)", (channel.id, channel.type))
        conn.commit()
        cursor.close()

        self.check_channels(True)

    def disable_channel(self, channel_id):
        conn = self.conn
        if conn is None:
            return

        cursor = conn.cursor()
        cursor.execute("DELETE FROM program_texts WHERE program_id IN (SELECT program_id FROM programs WHERE channel_id = (SELECT channel_id FROM channels WHERE asset_id = ?))", (channel_id,))
        cursor.execute("DELETE FROM program_genres WHERE program_id IN (SELECT program_id FROM programs WHERE channel_id = (SELECT channel_id FROM channels WHERE asset_id = ?))", (channel_id,))
        cursor.execute("DELETE FROM programs WHERE channel_id = (SELECT channel_id FROM channels WHERE asset_id = ?)", (channel_id,))
        cursor.execute("DELETE FROM channels WHERE asset_id = ?", (channel_id,))
        conn.commit()
        cursor.close()

        self.check_programs(True)

    def get_channels(self, update_date_offset=None):
        conn = self.conn
        if conn is None:
            return

        cursor = conn.cursor()
        if update_date_offset is not None:
            cursor.execute("SELECT asset_id FROM channels WHERE (updateDate + ?) < CAST(strftime('%s','now') AS INTEGER)", (update_date_offset,))
        else:
            cursor.execute("SELECT asset_id FROM channels")
        rows = cursor.fetchall()
        channels = [row['asset_id'] for row in rows]
        cursor.close()

        return channels

    def check_channels(self, load=False):
        if load:
            self.channel_ids = self.get_channels(86400) # 1 day
        return self.channel_ids and len(self.channel_ids) > 0

    def process_channel(self, service):
        conn = self.conn
        if conn is None:
            return

        session_id = service.addon.getSetting('session_id')
        channel_id = self.channel_ids[0]

        result = service.request.get_elem_epg_data(session_id, channel_id)
        if service.request.error:
            if service.request.recoverable:
                service.set_session_status(SessionStatus.INACTIVE)
                return
            else:
                xbmc.log("KyivstarArchive process_channel: error occurred while downloading asset %s epg data." % (channel_id), xbmc.LOGERROR)
                del self.channel_ids[0]
                return

        del self.channel_ids[0]
        if len(result) == 0:
            return

        channels = service.get_enabled_channels()
        channel = next((ch for ch in channels if ch.id == channel_id), None)

        if channel is None:
            self.disable_channel(channel_id)
            return

        xbmc.log("KyivstarArchive: processing channel %s(%s), queued %s" % (channel.id, channel.name, len(self.channel_ids)), xbmc.LOGDEBUG)

        self.update_programs(channel, result)

    def get_program_image(self, index):
        conn = self.conn
        if conn is None:
            return ''

        cursor = conn.cursor()
        cursor.execute("SELECT url FROM images WHERE image_id = ?", (index,))
        row = cursor.fetchone()
        cursor.close()

        if row is None:
            return ''

        return row['url']

    def set_program_image(self, url):
        conn = self.conn
        if conn is None:
            return -1

        cursor = conn.cursor()
        cursor.execute("SELECT image_id FROM images WHERE url = ?", (url,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("INSERT INTO images (url) VALUES (?)", (url,))
            index = cursor.lastrowid
            conn.commit()
        else:
            index = row['image_id']
        cursor.close()

        return index

    def get_program_genres(self, program_id):
        conn = self.conn
        if conn is None:
            return []

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM genres WHERE genre_id IN (SELECT genre_id FROM program_genres WHERE program_id = (SELECT program_id FROM programs WHERE asset_id = ?))", (program_id,))
        rows = cursor.fetchall()
        genres = [row['name'] for row in rows]
        cursor.close()

        return genres

    def set_program_genres(self, program_id, genres):
        conn = self.conn
        if conn is None:
            return

        cursor = conn.cursor()
        for genre in genres:
            genre_index = self.cached_genres.get(genre)
            if genre_index is None:
                cursor.execute("SELECT genre_id FROM genres WHERE name = ?", (genre,))
                row = cursor.fetchone()
                if row is None:
                    cursor.execute("INSERT INTO genres (name) VALUES (?)", (genre,))
                    genre_index = cursor.lastrowid
                    conn.commit()
                else:
                    genre_index = row['genre_id']
                self.cached_genres[genre] = genre_index
            cursor.execute("INSERT OR IGNORE INTO program_genres (program_id, genre_id) VALUES ((SELECT program_id FROM programs WHERE asset_id = ?), ?)", (program_id, genre_index))
        conn.commit()
        cursor.close()

    def parse_program_genres(self, asset_info):
        conn = self.conn
        if conn is None:
            return set()

        if 'genresList' in asset_info:
            genres = asset_info['genresList']
        elif 'genre' in asset_info:
            genres = asset_info['genre']
            if len(genres) == 1:
                genres = genres[0].split(';')
        else:
            return set()

        return set(genres)

    def get_program_text(self, program_id, is_name, locale='uk_UA'):
        conn = self.conn
        if conn is None:
            return ''

        cursor = conn.cursor()
        cursor.execute("SELECT value FROM texts WHERE text_id IN (SELECT text_id FROM program_texts WHERE program_id = (SELECT program_id FROM programs WHERE asset_id = ?) AND is_name = ? AND locale = ?)", (program_id, 1 if is_name else 0, locale))
        row = cursor.fetchone()
        cursor.close()

        return row['value'] if row else ''

    def set_program_text(self, program_id, text, is_name, locale):
        conn = self.conn
        if conn is None:
            return

        cursor = conn.cursor()
        cursor.execute("SELECT text_id FROM texts WHERE value = ?", (text,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO texts (value) VALUES (?)", (text,))
            text_index = cursor.lastrowid
            conn.commit()
        else:
            text_index = row['text_id']
        cursor.execute("INSERT OR REPLACE INTO program_texts (program_id, locale, is_name, text_id) VALUES ((SELECT program_id FROM programs WHERE asset_id = ?), ?, ?, ?)", (program_id, locale, 1 if is_name else 0, text_index))
        conn.commit()
        cursor.close()

    def update_programs(self, channel, epg_data):
        conn = self.conn
        if conn is None:
            return

        cursor = conn.cursor()
        cursor.execute("SELECT channel_id FROM channels WHERE asset_id = ?", (channel.id,))
        row = cursor.fetchone()
        if row is None:
            return

        channel_index = row['channel_id']

        data = {}
        for epg_day_data in epg_data:
            for program in epg_day_data.get('programList', []):
                program_id = program['assetId']
                locale = program.get('locale', 'uk_UA')
                record = data.get(program_id)
                if record is None:
                    cursor.execute("SELECT * FROM programs WHERE asset_id = ?", (program_id,))
                    row = cursor.fetchone()
                    if row is None:
                        record = {
                            'asset_id': program_id,
                            'channel_id': channel_index,
                            'start': int(program.get('start', 0)),
                            'parse_step': 0,
                            'release_date': 0,
                            'duration': int(program.get('duration', 0)) * 60,
                            'image_id': self.set_program_image(channel.logo),
                            'insert': True,
                            'update': set(['asset_id', 'channel_id', 'start', 'parse_step', 'release_date', 'duration', 'image_id']),
                            'locale': locale,
                            'name': program.get('title', ''),
                            'plot': strip_html(program.get('desc', '')),
                            'genres': self.parse_program_genres(program),
                            'update_external': set(['genres', 'name', 'plot']),
                        }
                        data[program_id] = record
                        continue
                    record = dict(row)
                    record['insert'] = False
                    record['update'] = set()
                    record['locale'] = locale
                    record['name'] = self.get_program_text(program_id, True, locale)
                    record['plot'] = self.get_program_text(program_id, False, locale)
                    record['genres'] = set(self.get_program_genres(program_id))
                    record['update_external'] = set()
                    data[program_id] = record

                start = int(program.get('start', 0))
                if record['start'] < start:
                    record['channel_id'] = channel_index
                    record['start'] = start
                    record['update'].add('channel_id')
                    record['update'].add('start')
                genres = self.parse_program_genres(program)
                if len(genres - record['genres']) > 0:
                    record['genres'] |= genres
                    record['update_external'].add('genres')
                duration = int(program.get('duration', 0)) * 60
                if record['duration'] == 0 and duration != 0:
                    record['duration'] = duration
                    record['update'].add('duration')
                title = program.get('title', '')
                if record['name'] == '' and title != '':
                    record['name'] = title
                    record['update_external'].add('name')
                desc = program.get('desc', '')
                if record['plot'] == '' and desc != '':
                    record['plot'] = strip_html(desc)
                    record['update_external'].add('plot')

        for record in data.values():
            if record['insert']:
                updates = list(record['update'])
                cursor.execute("INSERT INTO programs (%s) VALUES (%s)" % (', '.join(updates), ', '.join(['?'] * len(updates))),
                               tuple([record[field] for field in record['update']]))
            elif len(record['update']) > 0:
                updates = ["%s = ?" % field for field in record['update']]
                cursor.execute("UPDATE programs SET %s WHERE asset_id = ?" % ', '.join(updates), 
                               tuple([record[field] for field in record['update']]) + (record['asset_id'],))
            if 'genres' in record['update_external']:
                self.set_program_genres(record['asset_id'], record['genres'])
            if 'name' in record['update_external']:
                self.set_program_text(record['asset_id'], record['name'], True, record['locale'])
            if 'plot' in record['update_external']:
                self.set_program_text(record['asset_id'], record['plot'], False, record['locale'])
        conn.commit()

        dt = datetime.datetime.now() - datetime.timedelta(days=3)
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        timestamp = time.mktime(dt.timetuple())
        cursor.execute("DELETE FROM programs WHERE start < ?", (timestamp,))
        conn.commit()

        cursor.execute("UPDATE channels SET updateDate = CAST(strftime('%s','now') AS INTEGER) WHERE asset_id = ?", (channel.id,))
        conn.commit()

        cursor.close()

        self.check_programs(True)

    def check_programs(self, load=False):
        conn = self.conn
        if load and conn:
            cursor = conn.cursor()
            cursor.execute("SELECT asset_id FROM programs WHERE parse_step = 0 AND (SELECT type FROM channels WHERE channels.channel_id = programs.channel_id) = 'VIRTUAL'")
            rows = cursor.fetchall()
            self.program_ids = [row['asset_id'] for row in rows]
            cursor.close()
        return self.program_ids and len(self.program_ids) > 0

    def process_program(self, service):
        conn = self.conn
        if conn is None:
            return

        locale = service.addon.getSetting('locale')

        session_id = service.addon.getSetting('session_id')
        program_id = self.program_ids[0]

        result = service.request.get_asset_info(session_id, program_id)
        if service.request.error:
            if service.request.recoverable:
                service.set_session_status(SessionStatus.INACTIVE)
                return
            else:
                xbmc.log("KyivstarArchive process_program: error occurred while downloading asset %s data." % (program_id), xbmc.LOGERROR)
                del self.program_ids[0]
                return

        del self.program_ids[0]
        if len(result) == 0:
            return

        program = result[0]

        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM programs WHERE asset_id = ?", (program_id,)).fetchone()
        record = dict(row)
        record['parse_step'] = 1
        record['update'] = set(['parse_step'])
        record['name'] = self.get_program_text(program_id, True, locale)
        record['genres'] = set(self.get_program_genres(program_id))

        xbmc.log("KyivstarArchive: processing program %s(%s), queued %s" % (program_id, record['name'], len(self.program_ids)), xbmc.LOGDEBUG)

        release = program.get('releaseDate', 0)
        if release != 0:
            record['release_date'] = release
            record['update'].add('release_date')
        duration = int(program.get('duration', 0))
        if duration != 0:
            record['duration'] = duration
            record['update'].add('duration')
        image = next(iter([i['url'] for i in program.get('images',[]) if '2_3_XL' in i['url']]), '')
        if image != '':
            record['image_id'] = self.set_program_image(image)
            record['update'].add('image_id')
        if len(record['update']) > 0:
            updates = ["%s = ?" % field for field in record['update']]
            cursor.execute("UPDATE programs SET %s WHERE asset_id = ?" % ', '.join(updates),
                           tuple([record[field] for field in record['update']]) + (record['asset_id'],))

        name = program.get('name', '')
        if program.get('assetType', '') == 'EPISODE':
            series_name = program.get('seriesName', '')
            season = { 'en_US' : 'season', 'uk_UA' : 'сезон', 'ru_RU' : 'сезон' }
            season_number = program.get('seasonNumber', 0)
            episode = { 'en_US' : 'episode', 'uk_UA' : 'серія', 'ru_RU' : 'серия' }
            episod_number = program.get('episodeNumber', 0)
            if series_name != '' and season_number != 0 and episod_number != 0:
                name = '%s, %s %s, %s %s' % (series_name, season[locale], season_number, episode[locale], episod_number)
        if name != '':
            record['name'] = name
            self.set_program_text(record['asset_id'], record['name'], True, locale)
        plot = strip_html(program.get('plot', ''))
        if plot != '':
            record['plot'] = plot
            self.set_program_text(record['asset_id'], record['plot'], False, locale)
        genres = self.parse_program_genres(program)
        if len(genres - record['genres']) > 0:
            record['genres'] |= genres
            self.set_program_genres(record['asset_id'], record['genres'])

        conn.commit()

    def get_filters(self, filter_type):
        conn = self.conn
        if conn is None:
            return []

        cursor = conn.cursor()
        if filter_type == 'genre':
            cursor.execute("SELECT name FROM genres ORDER BY name")
            rows = cursor.fetchall()
            filters = [row['name'] for row in rows]
        elif filter_type == 'year':
            cursor.execute("SELECT DISTINCT release_date FROM programs WHERE release_date > 0 ORDER BY release_date DESC")
            rows = cursor.fetchall()
            filters = [row['release_date'] for row in rows]
        elif filter_type == 'duration':
            filters = ['0-30', '30-60', '60-90', '90-120', '120-150', '150-180', '180-0']
        elif filter_type == 'channel':
            filters = self.get_channels()
        else:
            filters = []
        cursor.close()

        return filters

    def get_elements(self, args, service):
        conn = self.conn
        if conn is None:
            return []

        locale = service.addon.getSetting('locale')

        if 'filters' not in args:
            args['filters'] = []
        filters = args['filters']
        sort = args.get('sort', ['name'])[0]
        sort_order = args.get('order', ['asc'])[0]
        offset = int(args.get('offset', [0])[0])
        limit = int(args.get('limit', [20])[0])
        select = args.get('select', [None])[0]

        cursor = conn.cursor()
        query = "SELECT * FROM programs"
        params = []

        if sort not in ['name', 'release_date', 'duration', 'channel_id']:
            sort = 'name'

        if sort == 'name':
            query += " JOIN program_texts AS t1 ON programs.program_id = t1.program_id AND t1.is_name = 1 AND t1.locale = ?"
            params.append(locale)
            query += " JOIN texts AS t2 ON t1.text_id = t2.text_id"
            sort = 't2.value'

        if len(filters) > 0:
            query += " WHERE "

        xbmc.log("KyivstarArchive: get elements with filters %s" % ', '.join(filters), xbmc.LOGDEBUG)

        channel_filters = []
        genre_filters = []
        year_filters = []
        duration_filters = []
        for filter in filters:
            filter = filter.split(':')
            filter_type = filter[0]
            filter = filter[1]
            if filter_type == 'channel':
                channel_filters.append(filter)
            elif filter_type == 'genre':
                genre_filters.append(filter)
            elif filter_type == 'year':
                year_filters.append(int(filter))
            elif filter_type == 'duration':
                duration_filters.append(filter)

        no_filter = len(params)

        if len(channel_filters) > 0:
            query += " channel_id IN (SELECT channel_id FROM channels WHERE asset_id IN (%s))" % ','.join(['?'] * len(channel_filters))
            params.extend(channel_filters)

        if len(genre_filters) > 0:
            if len(params) != no_filter:
                query += " AND "
            query += " programs.program_id IN (SELECT program_id FROM program_genres WHERE genre_id IN (SELECT genre_id FROM genres WHERE name IN (%s)))" % ','.join(['?'] * len(genre_filters))
            params.extend(genre_filters)

        if len(year_filters) > 0:
            if len(params) != no_filter:
                query += " AND "
            query += " release_date IN (%s)" % ','.join(['?'] * len(year_filters))
            params.extend(year_filters)

        if len(duration_filters) > 0:
            if len(params) != no_filter:
                query += " AND "
            duration_clauses = []
            for duration_filter in duration_filters:
                duration_filter = duration_filter.split('-')
                min_duration = int(duration_filter[0]) * 60
                max_duration = int(duration_filter[1]) * 60
                if min_duration == 0:
                    duration_clauses.append("duration <= ?")
                    params.append(max_duration)
                elif max_duration == 0:
                    duration_clauses.append("duration >= ?")
                    params.append(min_duration)
                else:
                    duration_clauses.append("(duration >= ? AND duration <= ?)")
                    params.append(min_duration)
                    params.append(max_duration)
            query += " (" + " OR ".join(duration_clauses) + ")"

        query += " ORDER BY %s %s" % (sort, 'ASC' if sort_order == 'asc' else 'DESC')

        query += " LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)

        xbmc.log("KyivstarArchive: executing query %s with params %s" % (query, params), xbmc.LOGDEBUG)

        cursor.execute(query, tuple(params))
        elements = cursor.fetchall()
        for i, element in enumerate(elements):
            element = dict(element)
            row = cursor.execute("SELECT * FROM channels WHERE channel_id = ?", (element['channel_id'],)).fetchone()
            element['videoid'] = '%s-%s|%s' % (row['asset_id'], row['type'], int(element['start']/1000))
            element['image'] = self.get_program_image(element['image_id'])
            element['name'] = self.get_program_text(element['asset_id'], True, locale)
            element['plot'] = self.get_program_text(element['asset_id'], False, locale)
            element['genres'] = self.get_program_genres(element['asset_id'])
            elements[i] = element

        cursor.close()

        return elements

    def vacuum(self):
        conn = self.conn
        if conn is None:
            return

        cursor = conn.cursor()
        cursor.execute("VACUUM")
        cursor.close()

    def close(self):
        conn = self.conn
        if conn:
            conn.close()
