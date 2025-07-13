import threading

import xbmc

from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from resources.lib.kyivstar_stream_manager import KyivstarStreamManager

class HttpGetHandler(BaseHTTPRequestHandler):
    def handle_get_playlist(self, url_query):
        query = parse_qs(url_query)
        asset_id = query['asset'][0]
        epg = query.get('epg', None)
        if epg:
            epg = epg[0]

        if hasattr(self.server, 'manager'):
            delattr(self.server, 'manager')

        self.server.manager = KyivstarStreamManager(self.server, asset_id, epg)
        return 'application/vnd.apple.mpegurl', self.server.manager.get_playlist_content()

    def handle_get_chunklist(self, url_query):
        live = False
        strip_length = 4
        if url_query.startswith('live&'):
            live = True
            strip_length += 5
        stream_url = url_query[strip_length:]
        return 'application/vnd.apple.mpegurl', self.server.manager.get_chunklist_content(stream_url, live)

    def do_GET(self):
        xbmc.log("KyivstarLiveStreamServer: GET %s" % self.path, xbmc.LOGDEBUG)

        content = None
        content_type = ''
        url = urlparse(self.path)
        if url.path == '/playlist.m3u8':
            content_type, content = self.handle_get_playlist(url.query)
        elif url.path == '/chunklist.m3u8':
            content_type, content = self.handle_get_chunklist(url.query)

        if content:
            if len(content) > 0:
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(204)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

class KyivstarHttpServer(object):
    def __init__(self, service):
        self.service = service
        self.server_thread = None
        HTTPServer.allow_reuse_address = True

    def start(self):
        try:
            port = int(self.service.addon.getSetting('live_stream_server_port'))
            self.httpd = HTTPServer(('', port), HttpGetHandler)
            self.httpd.service = self.service
            self.server_thread = threading.Thread(target=self.process)
            self.server_thread.start()
            xbmc.log("KyivstarHttpServer: started at 0.0.0.0:%s" % port, xbmc.LOGINFO)
        except Exception as e:
            xbmc.log("KyivstarHttpServer exception %s" % str(e), xbmc.LOGERROR)

    def process(self):
        try:
            self.httpd.serve_forever()
        except Exception as e:
            xbmc.log("KyivstarHttpServer exception %s" % str(e), xbmc.LOGERROR)

    def stop(self):
        if not self.server_thread:
            return

        self.httpd.shutdown()
        self.httpd.server_close()
        self.server_thread.join()

        self.httpd = None
        self.server_thread = None

        xbmc.log("KyivstarHttpServer: stoped", xbmc.LOGINFO)
