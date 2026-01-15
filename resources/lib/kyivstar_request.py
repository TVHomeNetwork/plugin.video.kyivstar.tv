import requests
import xbmc
from datetime import datetime, timedelta

class KyivstarRequest:
    def __init__(self, device_id, locale):
        self.base_api_url = "https://clients.production.vidmind.com/vidmind-stb-ws/{}"
        self.base_local_url = None
        self.base_auth_url = "https://kyivstar-auth.production.vidmind.com/kyivstar-auth/{}"
        self.headers = headers = {
            'Origin': 'https://tv.kyivstar.ua',
            'Referer': 'https://tv.kyivstar.ua/',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0',
            'x-vidmind-device-id': device_id,
            'x-vidmind-device-type': 'WEB',
            'x-vidmind-locale': locale,
            }
        self.error = None
        self.recoverable = True
        self.url = None

    def set_base_local_url_port(self, port):
        self.base_local_url = "http://127.0.0.1:%s/{}" % port

    def send(self, url, data=None, json=None, ret=True, ret_json=True, cookies=None):
        result = None
        self.error = None
        self.recoverable = True
        self.url = url
        try:
            if data is None and json is None:
                response = requests.get(url, headers=self.headers, cookies=cookies)
            elif data is not None:
                response = requests.post(url, data=data, headers=self.headers, cookies=cookies)
            elif json is not None:
                response = requests.post(url, json=json, headers=self.headers, cookies=cookies)
            if ret:
                if response.status_code == 200:
                    result = response.json() if ret_json else response.text
                else:
                    try:
                        result = response.json()
                    except:
                        result = response.text
                    self.error = 'An unexpected status code of response - %s' % response.status_code
                    self.recoverable = False
            else:
                if response.status_code == 204:
                    result = True
                else:
                    try:
                        result = response.json()
                    except:
                        result = response.text
                    self.error = 'An unexpected status code of response - %s' % response.status_code
                    self.recoverable = False
            if len(response.history) > 0:
                self.url = response.history[0].headers['Location']
            response.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self.error = str(e)
        except requests.exceptions.HTTPError as e:
            self.error = str(e)
            if e.response.status_code not in [500, 502, 503, 504]:
                self.recoverable = False
        except Exception as e:
            self.error = str(e)
            self.recoverable = False
        finally:
            return result

# Post requests

    def login_anonymous(self):
        url = self.base_api_url.format('authentication/login')
        obj_data = {
            'username' : '557455cfe4b04ad886a6ae41\\anonymous',
            'password' : 'anonymous'
        }
        result = self.send(url, data=obj_data)
        if self.error:
            xbmc.log("KyivstarRequest exception in login_anonymous: " + self.error, xbmc.LOGERROR)
            return {}
        return result

    #otp = one time password(sms code)
    def login(self, session_id, username, password=None, otp=None):
        url = self.base_api_url.format('authentication/login/v3;jsessionid=%s' % session_id)
        obj_data = { 'username' : '557455cfe4b04ad886a6ae41\\%s' % username }
        if password:
            obj_data['password'] = password
        elif otp:
            obj_data['otp'] = otp
        else:
            return {}
        result = self.send(url, data=obj_data)
        if self.error:
            xbmc.log("KyivstarRequest exception in login: " + self.error, xbmc.LOGERROR)
            return {}
        return result

    def send_auth_otp(self, session_id, phonenumber):
        url = self.base_api_url.format('v2/otp;jsessionid=%s' % session_id)
        json_data = {
            'phoneNumber' : phonenumber,
            'language' : 'UK',
            'channel' : 'sms'
        }
        result = self.send(url, json=json_data, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in send_auth_otp: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def get_elem_cur_program_epg_data(self, session_id, elem_id):
        url = self.base_api_url.format('livechannels/current-programs;jsessionid=%s' % session_id)
        json_data = { 'assetIds' : [elem_id] }
        result = self.send(url, json=json_data)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_elem_cur_program_epg_data: " + self.error, xbmc.LOGERROR)
            return {}
        return result[0] if len(result) > 0 else {}

    # locale: en_US, uk_UA, ru_RU
    def change_locale(self, session_id, locale):
        url = self.base_api_url.format('subscribers/locale/change;jsessionid=%s' % session_id)
        json_data = { 'locale' : locale }
        result = self.send(url, json=json_data, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in change_locale: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def get_content_area_filters(self, session_id, area_id):
        url = self.base_api_url.format('filters;jsessionid=%s' % session_id)
        json_data = { 'contentAreaId' : area_id }
        result = self.send(url, json=json_data)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_content_area_filters: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_compilations(self, session_id, area_id):
        url = self.base_api_url.format('compilations;jsessionid=%s' % session_id)
        json_data = {
            'contentAreaId' : area_id,
            'compilationGroupType' : 'CRISPS'
        }
        result = self.send(url, json=json_data)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_compilations: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_content_area_elems(self, session_id, compilation, filters, sort, offset, limit, sort_order=None):
        url = self.base_api_url.format('gallery/filters/content-area;jsessionid=%s' % session_id)
        json_data = {
            'compilationElementId' : compilation,
            'filterElementIds' : filters,
            'filterSortElementId' : sort,
            'offset' : offset,
            'limit' : limit,
            'sortOrder' : sort_order
        }
        result = self.send(url, json=json_data)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_content_area_elems: " + self.error, xbmc.LOGERROR)
            return []
        return result

# Get requests

    def logout(self, session_id):
        url = self.base_api_url.format('authentication/logout;jsessionid=%s?sessionExpired=false' % session_id)
        result = self.send(url, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in logout: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def get_profiles(self, session_id):
        url = self.base_api_url.format('api/v1/subscribers;jsessionid=%s' % session_id)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_profiles: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_content_areas(self, session_id):
        url = self.base_api_url.format('contentareas;jsessionid=%s' % session_id)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_content_areas: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_sort_filters(self, session_id):
        url = self.base_api_url.format('filters/sort-elements;jsessionid=%s' % session_id)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_sort_filters: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_live_channels_groups(self, session_id):
        url = self.base_api_url.format('v1/contentareas/LIVE_CHANNELS;jsessionid=%s?includeRestricted=true&limit=100' % session_id)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_live_channels_groups: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_group_elems(self, session_id, group_id):
        url = self.base_api_url.format('gallery/contentgroups/%s;jsessionid=%s?offset=0&limit=500' % (group_id, session_id))
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_group_elems: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_elem_epg_data(self, session_id, elem_id, date=None, days_before=3, days_after=3):
        now_date = datetime.now() if date is None else date
        next_date = (now_date + timedelta(days=days_after)).strftime('%Y%m%d')
        prev_date = (now_date - timedelta(days=days_before)).strftime('%Y%m%d')
        url = self.base_api_url.format('livechannels/%s/epg;jsessionid=%s?from=%s&to=%s' % (elem_id, session_id, prev_date, next_date))
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_elem_epg_data: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_elem_stream_url(self, user_id, session_id, elem_id, virtual=False, date=None):
        url = self.base_api_url.format('play/v%s;jsessionid=%s?assetId=%s' % ('4' if user_id == 'anonymous' else '2', session_id, elem_id))
        if date:
            url += '&date=%s' % date
        result = self.send(url)
        if result and 'error' in result:
            xbmc.log("KyivstarRequest exception in get_elem_stream_url: " + result.get('description', 'Unknown error'), xbmc.LOGERROR)
            return ''
        if self.error:
            xbmc.log("KyivstarRequest exception in get_elem_stream_url: " + self.error, xbmc.LOGERROR)
            return ''
        return result['media'][0]['url'] if virtual else result['liveChannelUrl']

    def get_elem_playback_stream_url(self, user_id, session_id, elem_id, date):
        url = self.base_api_url.format('livechannels/v%s/playback;jsessionid=%s?assetId=%s&date=%s' % ('4' if user_id == 'anonymous' else '2', session_id, elem_id, date))
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_elem_playback_stream_url: " + self.error, xbmc.LOGERROR)
            return ''
        return result['uri']

    def get_search(self, session_id, query):
        url = self.base_api_url.format('api/v1/search/predictive;jsessionid=%s?q=%s&limit=50&includeLiveChannels=true' % (session_id, query))
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_search: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_asset_info(self, session_id, asset_id):
        url = self.base_api_url.format('assets/v2;jsessionid=%s?movie=%s' % (session_id, asset_id))
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_asset_info: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def get_asset_tvgroup_info(self, session_id, asset_id, season_number, offset, limit):
        url = self.base_api_url.format('api/v1/gallery/tvgroup/%s;jsessionid=%s?seasonNumber=%s&offset=%s&limit=%s' % (asset_id, session_id, season_number, offset, limit))
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_asset_tvgroup_info: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def local_get_channels(self):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('get_channels')
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_get_channels: " + self.error, xbmc.LOGERROR)
            return {}
        return result

    def local_get_channel(self, asset):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('get_channel?asset=%s' % asset)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_get_channel: " + self.error, xbmc.LOGERROR)
            return {}
        return result

    def local_update_channel(self, asset, _property, value):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('update_channel?asset=%s&property=%s&value=%s' % (asset, _property, value))
        result = self.send(url, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_update_channel: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def local_move_channel(self, asset, position):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('move_channel?asset=%s&position=%s' % (asset, position))
        result = self.send(url, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_move_channel: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def local_execute(self, command):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('execute?command=%s' % command)
        result = self.send(url, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_execute: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def local_get_archive(self, args):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('get_archive?%s' % args)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_get_archive: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def local_get_archive_videoid(self, program_asset_id):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('get_archive_videoid?program_asset_id=%s' % program_asset_id)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_get_archive_videoid: " + self.error, xbmc.LOGERROR)
            return ''
        return result

    def local_get_archive_channels(self):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('get_archive_channels')
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_get_archive_channels: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def local_set_archive_channels(self, channels):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('set_archive_channels?%s' % channels)
        result = self.send(url, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_set_archive_channels: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def local_get_archive_filters(self, _type):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('get_archive_filters?type=%s' % _type)
        result = self.send(url)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_get_archive_filters: " + self.error, xbmc.LOGERROR)
            return []
        return result

    def local_reset_archive(self):
        if self.base_local_url is None:
            return None
        url = self.base_local_url.format('reset_archive')
        result = self.send(url, ret=False)
        if self.error:
            xbmc.log("KyivstarRequest exception in local_reset_archive: " + self.error, xbmc.LOGERROR)
            return False
        return result

    def generate_link(self, session_id):
        url = self.base_auth_url.format('access-code/generate/link')
        cookies = { 'JSESSIONID': session_id }
        result = self.send(url, data={}, cookies=cookies)
        if self.error:
            xbmc.log("KyivstarRequest exception in generate_link: " + self.error, xbmc.LOGERROR)
            return {}
        return result

    def subscriber_signed_in(self, session_id):
        url = self.base_auth_url.format('subscriber/signed-in')
        cookies = { 'JSESSIONID': session_id }
        result = self.send(url, ret_json=False, cookies=cookies)
        if self.error:
            if '403' not in self.error:
                xbmc.log("KyivstarRequest exception in subscriber_signed_in: " + self.error, xbmc.LOGERROR)
            return False
        return True

    def get_profile(self, session_id):
        url = self.base_api_url.format('api/v1/subscribers/me')
        cookies = { 'JSESSIONID': session_id }
        result = self.send(url, cookies=cookies)
        if self.error:
            xbmc.log("KyivstarRequest exception in get_profile: " + self.error, xbmc.LOGERROR)
            return {}
        return result
