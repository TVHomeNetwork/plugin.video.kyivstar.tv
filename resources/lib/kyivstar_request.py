import requests
import xbmc
from datetime import datetime, timedelta

class KyivstarRequest:
    def __init__(self, device_id, locale):
        self.base_api_url = "https://clients.production.vidmind.com/vidmind-stb-ws/{}"
        self.headers = headers = {
            'Origin': 'https://tv.kyivstar.ua',
            'Referer': 'https://tv.kyivstar.ua/',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0',
            'x-vidmind-device-id': device_id,
            'x-vidmind-device-type': 'WEB',
            'x-vidmind-locale': locale,
            }

# Post requests

    def login_anonymous(self):
        profile = {}
        try:
            url = self.base_api_url.format('authentication/login')
            obj_data = {
                'username':'557455cfe4b04ad886a6ae41\\anonymous',
                'password':'anonymous'
                }
            response = requests.post(url, data=obj_data, headers=self.headers)
            if response.status_code == 200:
                profile = response.json()
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in login_anonymous: " + str(e), xbmc.LOGERROR)
        finally:
            return profile

    #otp = one time password(sms code)
    def login(self, session_id, username, password=None, otp=None):
        profile = {}
        try:
            obj_data = {'username':'557455cfe4b04ad886a6ae41\\%s' % username}
            if password:
                obj_data['password'] = password
            elif otp:
                obj_data['otp'] = otp
            else:
                return profile
            url = self.base_api_url.format('authentication/login/v3;jsessionid=%s' % session_id)
            response = requests.post(url, data=obj_data, headers=self.headers)
            if response.status_code == 200:
                profile = response.json()
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in login: " + str(e), xbmc.LOGERROR)
        finally:
            return profile

    def send_auth_otp(self, session_id, phonenumber):
        result = False
        try:
            url = self.base_api_url.format('v2/otp;jsessionid=%s' % session_id)
            json_data = {
                'phoneNumber':phonenumber,
                'language':'UK'
                }
            response = requests.post(url, json=json_data, headers=self.headers)
            if response.status_code == 204:
                result = True
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in send_auth_otp: " + str(e), xbmc.LOGERROR)
        finally:
            return result

    def get_elem_cur_program_epg_data(self, session_id, elem_id):
        epg_data = {}
        try:
            json_data = {
                'assetIds':[elem_id]
                }
            url = self.base_api_url.format('livechannels/current-programs;jsessionid=%s' % session_id)
            response = requests.post(url, json=json_data, headers=self.headers)
            if response.status_code == 200:
                response_data = response.json()
                if len(response_data) > 0:
                    epg_data = response_data[0]
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in get_elem_cur_program_epg_data: " + str(e), xbmc.LOGERROR)
        finally:
            return epg_data

    # locale: en_US, uk_UA, ru_RU
    def change_locale(self, session_id, locale):
        result = False
        try:
            url = self.base_api_url.format('subscribers/locale/change;jsessionid=%s' % session_id)
            json_data = {
                'locale':locale
                }
            response = requests.post(url, json=json_data, headers=self.headers)
            if response.status_code == 204:
                result = True
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in change_locale: " + str(e), xbmc.LOGERROR)
        finally:
            return result

# Get requests

    def logout(self, session_id):
        result = False
        try:
            url = self.base_api_url.format('authentication/logout;jsessionid=%s?sessionExpired=false' % session_id)
            response = requests.get(url, headers=self.headers)
            if response.status_code == 204:
                result = True
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in logout: " + str(e), xbmc.LOGERROR)
        finally:
            return result

    def get_profiles(self, session_id):
        profiles = []
        try:
            url = self.base_api_url.format('api/v1/subscribers;jsessionid=%s' % session_id)
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                profiles = response.json()
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in get_profiles: " + str(e), xbmc.LOGERROR)
        finally:
            return profiles

    def get_live_channels_groups(self, session_id):
        groups = []
        try:
            url = self.base_api_url.format('v1/contentareas/LIVE_CHANNELS;jsessionid=%s?includeRestricted=true&limit=100' % session_id)
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                groups = response.json()
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in get_groups: " + str(e), xbmc.LOGERROR)
        finally:
            return groups

    def get_group_elems(self, session_id, group_id):
        elements = []
        try:
            url = self.base_api_url.format('gallery/contentgroups/%s;jsessionid=%s?offset=0&limit=500' % (group_id, session_id))
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                elements = response.json()
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in get_group_elems: " + str(e), xbmc.LOGERROR)
        finally:
            return elements

    def get_elem_epg_data(self, session_id, elem_id):
        epg_datas = []
        try:
            now_date = datetime.now()
            next_date = (now_date + timedelta(days=3)).strftime('%Y%m%d')
            prev_date = (now_date - timedelta(days=3)).strftime('%Y%m%d')
            url = self.base_api_url.format('livechannels/%s/epg;jsessionid=%s?from=%s&to=%s' % (elem_id, session_id, prev_date, next_date))
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                epg_datas = response.json()
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in get_elem_epg_data: " + str(e), xbmc.LOGERROR)
        finally:
            return epg_datas

    def get_elem_stream_url(self, user_id, session_id, elem_id, virtual=False, date=None):
        result = ''
        try:
            play_v = '2'
            if user_id == 'anonymous':
                play_v = '4'
            url = self.base_api_url.format('play/v%s;jsessionid=%s?assetId=%s' % (play_v, session_id, elem_id))
            if date:
                url += '&date=%s' % date
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                if virtual:
                    result = response.json()['media'][0]['url']
                else:
                    result = response.json()['liveChannelUrl']
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in get_elem_stream_url: " + str(e), xbmc.LOGERROR)
        finally:
            return result

    def get_elem_playback_stream_url(self, user_id, session_id, elem_id, date):
        result = ''
        try:
            play_v = '2'
            if user_id == 'anonymous':
                play_v = '4'
            url = self.base_api_url.format('livechannels/v%s/playback;jsessionid=%s?assetId=%s&date=%s' % (play_v, session_id, elem_id, date))
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                result = response.json()['uri']
            else:
                response.raise_for_status()
        except Exception as e:
            xbmc.log("KyivstarRequest exception in get_elem_stream_url: " + str(e), xbmc.LOGERROR)
        finally:
            return result
