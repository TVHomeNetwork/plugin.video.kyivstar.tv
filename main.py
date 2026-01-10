import sys
import requests
import routing
import time
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from urllib.parse import quote, parse_qs, urlencode
from resources.lib.kyivstar_service import KyivstarService
from resources.lib.common import SessionStatus, strip_html

service = KyivstarService()
plugin = routing.Plugin()
handle = int(sys.argv[1])

class LoginDialog(xbmcgui.WindowDialog):
    def __init__(self, phonenumber, username, password):
        height = self.getHeight()
        width = self.getWidth()
        
        window_height = int(height/2)
        window_width = int(width/2)
        margin = 10
        control_height = int(window_height/5)
        control_width = window_width
        control_width_half = int(window_width/2)

        x = int(width/4)
        y = int(height/4)

        texture = service.addon.getAddonInfo('path') + '/resources/images/background.jpg'
        self.image0 = xbmcgui.ControlImage(x - margin, y - margin, window_width + 2*margin, window_height + 2*margin, texture)
        self.addControl(self.image0)

        texture = service.addon.getAddonInfo('path') + '/resources/images/head-button.png'
        texture_focus = service.addon.getAddonInfo('path') + '/resources/images/head-button-focus.png'
        loc_str = service.addon.getLocalizedString(30100) # "Phone number"
        self.select0 = xbmcgui.ControlButton(x + margin, y + margin, control_width_half - margin, control_height - 2*margin, loc_str, noFocusTexture=texture, focusTexture=texture_focus)
        self.addControl(self.select0)

        x += control_width_half
        loc_str = service.addon.getLocalizedString(30101) # "Personal account"
        self.select1 = xbmcgui.ControlButton(x, y + margin, control_width_half - margin, control_height - 2*margin, loc_str, noFocusTexture=texture, focusTexture=texture_focus)
        self.addControl(self.select1)

        x -= control_width_half
        y += control_height
        texture = service.addon.getAddonInfo('path') + '/resources/images/edit.png'
        loc_str = service.addon.getLocalizedString(30102) # "Username:"
        self.edit_username = xbmcgui.ControlEdit(x + margin, y + margin, control_width - 2*margin, control_height - 2*margin, loc_str, _alignment=4, noFocusTexture=texture, focusTexture=texture)
        self.edit_username.setText(username)
        self.addControl(self.edit_username)

        loc_str = service.addon.getLocalizedString(30104) # "Phonenumber:"
        self.edit_phonenumber = xbmcgui.ControlEdit(x + margin, y + margin + int(control_height/2), control_width - 2*margin, control_height - 2*margin, loc_str, _alignment=4, noFocusTexture=texture, focusTexture=texture)
        self.edit_phonenumber.setText(phonenumber)
        self.addControl(self.edit_phonenumber)

        y += control_height
        loc_str = service.addon.getLocalizedString(30103) # "Password:"
        self.edit_password = xbmcgui.ControlEdit(x + margin, y + margin, control_width - 2*margin, control_height - 2*margin, loc_str, _alignment=4, noFocusTexture=texture, focusTexture=texture)
        self.edit_password.setText(password)
        self.addControl(self.edit_password)

        y += control_height
        texture = service.addon.getAddonInfo('path') + '/resources/images/button.png'
        texture_focus = service.addon.getAddonInfo('path') + '/resources/images/button-focus.png'
        loc_str = service.addon.getLocalizedString(30105) # "Anonymous Login"
        self.button0 = xbmcgui.ControlButton(x + margin, y + margin, control_width - 2*margin, control_height - 2*margin, loc_str, alignment=6, noFocusTexture=texture, focusTexture=texture_focus)
        self.addControl(self.button0)

        y += control_height
        loc_str = service.addon.getLocalizedString(30107) # "Cancel"
        self.button1 = xbmcgui.ControlButton(x + margin, y + margin, control_width_half - 2*margin, control_height - 2*margin, loc_str, alignment=6, noFocusTexture=texture, focusTexture=texture_focus)
        self.addControl(self.button1)

        x += control_width_half
        loc_str = service.addon.getLocalizedString(30106) # "Login"
        self.button2 = xbmcgui.ControlButton(x + margin, y + margin, control_width_half - 2*margin, control_height - 2*margin, loc_str, alignment=6, noFocusTexture=texture, focusTexture=texture_focus)
        self.addControl(self.button2)
        
        self.select0.controlRight(self.select1)
        self.select0.controlDown(self.edit_username)
        self.select1.controlLeft(self.select0)
        self.select1.controlDown(self.edit_username)
        self.edit_username.controlUp(self.select0)
        self.edit_username.controlDown(self.edit_password)
        self.edit_password.controlUp(self.edit_username)
        self.edit_password.controlDown(self.edit_phonenumber)
        self.edit_phonenumber.controlUp(self.edit_password)
        self.edit_phonenumber.controlDown(self.button0)
        self.button0.controlUp(self.edit_phonenumber)
        self.button0.controlDown(self.button1)
        self.button1.controlUp(self.button0)
        self.button1.controlRight(self.button2)
        self.button2.controlUp(self.button0)
        self.button2.controlLeft(self.button1)

        self.setFocus(self.select0)

        self.active = True
        self.change_login_type(1)

    def change_login_type(self, login_type):
        self.login_type = login_type
        self.edit_username.setVisible(self.login_type == 2)
        self.edit_password.setVisible(self.login_type == 2)
        self.edit_phonenumber.setVisible(self.login_type == 1)

    def onControl(self, control):
        control_id = control.getId()
        if control_id == self.select0.getId():
            self.change_login_type(1)
            return
        if control_id == self.select1.getId():
            self.change_login_type(2)
            return
        if control_id == self.button0.getId():
            self.login_type = 3
        if control_id == self.button1.getId():
            self.login_type = 0
        if control_id == self.button2.getId():
            if self.login_type == 1 and self.edit_phonenumber.getText() == '':
                loc_str = service.addon.getLocalizedString(30200) # 'For login you must set phonenumber.'
                xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
                return
            if self.login_type == 2 and (self.edit_username.getText() == '' or self.edit_password.getText() == ''):
                loc_str = service.addon.getLocalizedString(30201) # 'For login you must set username and password.'
                xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
                return
        self.active=False
        self.close()

    def onAction(self, action):
        if action.getId() == xbmcgui.ACTION_PREVIOUS_MENU or action.getId() == xbmcgui.ACTION_NAV_BACK:
            self.login_type = 0
            self.active=False
            self.close()

@plugin.route('/login')
def login():
    if service.get_session_status() != SessionStatus.EMPTY:
        return

    phonenumber = service.addon.getSetting('phonenumber')
    username = service.addon.getSetting('username')
    password = service.addon.getSetting('password')

    login_form = LoginDialog(phonenumber, username, password)
    login_form.show()

    while login_form.active:
        xbmc.sleep(100)

    phonenumber = login_form.edit_phonenumber.getText()
    username = login_form.edit_username.getText()
    password = login_form.edit_password.getText()
    login_type = login_form.login_type

    del login_form

    if login_type == 0:
        return

    profile = service.request.login_anonymous()

    if 'userId' not in profile or 'sessionId' not in profile:
        loc_str = service.addon.getLocalizedString(30202) # 'Error during login. Check your logs for details.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
        return

    if login_type == 3:
        service.addon.setSetting('user_id', profile['userId'])
        service.addon.setSetting('session_id', profile['sessionId'])
        service.addon.setSetting('logged', 'true')
        service.set_session_status(SessionStatus.ACTIVE)
        return

    if login_type == 1:
        if not service.request.send_auth_otp(profile['sessionId'], phonenumber):
            loc_str = service.addon.getLocalizedString(30202) # 'Error during login. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            return

        otp = xbmcgui.Dialog().input('Enter secret code', type=xbmcgui.INPUT_NUMERIC)
        profile = service.request.login(profile['sessionId'], phonenumber, otp=otp)

        if 'userId' not in profile or 'sessionId' not in profile:
            loc_str = service.addon.getLocalizedString(30202) # 'Error during login. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            return

        service.addon.setSetting('user_id', profile['userId'])
        service.addon.setSetting('session_id', profile['sessionId'])
        service.addon.setSetting('phonenumber', phonenumber)
        service.addon.setSetting('logged', 'true')
        service.set_session_status(SessionStatus.ACTIVE)
    else:
        profile = service.request.login(profile['sessionId'], username, password=password)

        if 'userId' not in profile or 'sessionId' not in profile:
            loc_str = service.addon.getLocalizedString(30202) # 'Error during login. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            return

        service.addon.setSetting('user_id', profile['userId'])
        service.addon.setSetting('session_id', profile['sessionId'])
        service.addon.setSetting('username', username)
        service.addon.setSetting('logged', 'true')
        service.set_session_status(SessionStatus.ACTIVE)

@plugin.route('/logout')
def logout():
    loc_str_1 = service.addon.getLocalizedString(30110) # 'Logout'
    loc_str_2 = service.addon.getLocalizedString(30111) # 'Do you want to log out?'
    loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
    loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
    result = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
    if not result:
        return

    user_id = service.addon.getSetting('user_id')
    session_id = service.addon.getSetting('session_id')

    if user_id != 'anonymous' and not service.request.logout(session_id):
        loc_str = service.addon.getLocalizedString(30203) # 'Error during logout. Check your logs for details.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
        service.set_session_status(SessionStatus.INACTIVE)
        return

    service.addon.setSetting('logged', 'false')
    service.addon.setSetting('user_id', '')
    service.addon.setSetting('session_id', '')
    service.set_session_status(SessionStatus.EMPTY)

def get_local_elem_stream_url(asset_id, epg=None):
    service.request.error = None
    port = int(service.addon.getSetting('live_stream_server_port'))
    if epg is None:
        return 'http://127.0.0.1:%s/playlist.m3u8?asset=%s' % (port, asset_id)
    return 'http://127.0.0.1:%s/playlist.m3u8?asset=%s&epg=%s' % (port, asset_id, epg)

@plugin.route('/play/<videoid>')
def play(videoid):
    if service.get_session_status() == SessionStatus.EMPTY:
        loc_str = service.addon.getLocalizedString(30204) # 'Log in to the plugin'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    session_id = service.addon.getSetting('session_id')
    user_id = service.addon.getSetting('user_id')

    videoid, epg = videoid.split('|')
    asset_id, video_type = videoid.split('-')

    is_virtual = (video_type == 'VIRTUAL')
    is_live = (epg == 'null')

    epg_str = 'null' if is_live else time.strftime('%Y.%m.%d %H:%M:%S', time.gmtime(int(epg)))
    epg = None if is_live else epg + '000'

    xbmc.log("KyivstarPlay: asset_id = %s, video_type = %s, epg_time = %s(%s)" % (asset_id, video_type, epg, epg_str), xbmc.LOGINFO)

    use_stream_manager = (service.addon.getSetting('live_stream_server_enabled') == 'true')
    remove_ads = (service.addon.getSetting('remove_ads_in_catchup_mode') == 'true')

    url = ''
    if is_virtual:
        if (is_live and use_stream_manager) or (not is_live and remove_ads):
            url = get_local_elem_stream_url(asset_id, epg)
        else:
            url = service.request.get_elem_stream_url(user_id, session_id, asset_id, virtual=True, date=epg)
    else:
        if is_live:
            url = service.request.get_elem_stream_url(user_id, session_id, asset_id, virtual=False)
        else:
            url = service.request.get_elem_playback_stream_url(user_id, session_id, asset_id, epg)

    if service.request.error:
        loc_str = service.addon.getLocalizedString(30216) # 'Error getting stream url. Check your logs for details.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    if not url.startswith('http://127.0.0.1'):
        url += '|User-Agent="%s"' % service.request.headers['User-Agent']
        url += '&Referer="%s"' % service.request.headers['Referer']

    xbmc.log("KyivstarPlay: url = %s" % (url), xbmc.LOGINFO)

    play_item = xbmcgui.ListItem(path=url)
    play_item.setMimeType('application/vnd.apple.mpegurl')

    inputstream = service.addon.getSetting('stream_inputstream')
    if inputstream != 'default':
        play_item.setProperty('inputstream', inputstream)

    if inputstream == 'inputstream.ffmpegdirect':
        play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')
        play_item.setProperty('inputstream.ffmpegdirect.manifest_type', 'hls')
    elif inputstream == 'inputstream.adaptive':
        if not is_virtual and not is_live:
            #TODO: inputstream.ffmpegdirect need similar option for unfinished catchup
            play_item.setProperty('inputstream.adaptive.play_timeshift_buffer', 'true')

    if is_virtual and is_live and not use_stream_manager:
        # Set resume point of video to current time.
        cur_program_epg = service.request.get_elem_cur_program_epg_data(session_id, asset_id)
        if 'start' in cur_program_epg and 'finish' in cur_program_epg:
            duration = cur_program_epg['finish']/1000 - cur_program_epg['start']/1000
            live_point = time.time() - cur_program_epg['start']/1000
            video_info = play_item.getVideoInfoTag()
            video_info.setResumePoint(live_point, duration)

    xbmcplugin.setResolvedUrl(handle, True, listitem=play_item)

@plugin.route('/play_archive/<program_asset_id>')
def play_archive(program_asset_id):
    videoid = service.request.local_get_archive_videoid(program_asset_id)
    if service.request.error:
        loc_str = service.addon.getLocalizedString(30214) # 'Error accessing archive. Check your logs for details.'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    if not videoid:
        loc_str = service.addon.getLocalizedString(30215) # 'Program not found in archive'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    return play(videoid)

@plugin.route('')
def root():
    loc_str = service.addon.getLocalizedString(30521) # 'Search'
    li = xbmcgui.ListItem(label='[B]%s[/B]' % loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/search.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(search)
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    loc_str = service.addon.getLocalizedString(30522) # 'Videos'
    li = xbmcgui.ListItem(label='[B]%s[/B]' % loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/videos.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_videos, area=None)
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    loc_str = service.addon.getLocalizedString(30523) # 'Channel archive'
    li = xbmcgui.ListItem(label='[B]%s[/B]' % loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/archive.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_archive)
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    loc_str = service.addon.getLocalizedString(30500) # 'Channel manager'
    li = xbmcgui.ListItem(label='[B]%s[/B]' % loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/channel-manager.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_channel_manager)
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    loc_str = service.addon.getLocalizedString(30524) # 'Settings'
    li = xbmcgui.ListItem(label='[B]%s[/B]' % loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/settings.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_settings)
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, cacheToDisc=True)

def get_asset_list_item(asset, label=None):
    if label is None:
        label = asset.get('name', '')

    purchased = asset.get('purchased', True)
    if not purchased:
        label = f'[COLOR=red]{label}[/COLOR]'

    li = xbmcgui.ListItem(label=label)
    video_info = li.getVideoInfoTag()

    year = asset['release_date'] if 'release_date' in asset else asset.get('releaseDate')
    if year: video_info.setYear(year)

    rating = asset.get('ratings', [None])[0]
    if rating: video_info.setRating(rating['movieRating'], rating['numberOfVotes'], rating['ratingProviderType'].lower())

    duration = asset.get('duration')
    if duration: video_info.setDuration(duration)

    plot = asset['shortPlot'] if 'shortPlot' in asset else asset.get('plot')
    if plot: video_info.setPlot(strip_html(plot))

    title = asset.get('name')
    if title: video_info.setTitle(title)

    if 'image' in asset:
        image = asset['image']
    else:
        image = next(iter([i['url'] for i in asset['images'] if '2_3_XL' in i['url']]), '')
    li.setArt({'icon': image, 'fanart': service.addon.getAddonInfo('fanart')})

    return li

@plugin.route('/series/<asset_id>/<season>')
def show_series(asset_id, season):
    session_id = service.addon.getSetting('session_id')
    locale = service.addon.getSetting('locale')

    xbmcplugin.setContent(handle, 'videos')

    season = int(season)

    query = ''
    if len(sys.argv) > 2:
        query = sys.argv[2][1:]
    args = parse_qs(query)
    offset = int(args.get('offset', [0])[0])
    limit = int(args.get('limit', [20])[0])

    if season == 0:
        elem = service.request.get_asset_info(session_id, asset_id)
        if len(elem) == 0:
            xbmcplugin.endOfDirectory(handle, cacheToDisc=True)
            return

        elem = elem[0]
        season_name = { 'en_US' : 'Season', 'uk_UA' : 'Сезон', 'ru_RU' : 'Сезон' }
        for i in elem.get('seasons', []):
            loc_str = '%s %s' % (season_name[locale], i['number'])
            li = get_asset_list_item(elem, loc_str)
            li.setProperty('IsPlayable', 'false')
            url = plugin.url_for(show_series, asset_id=asset_id, season=i['number'])
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    else:
        elems = service.request.get_asset_tvgroup_info(session_id, asset_id, season, offset, limit)
        for elem in elems:
            li = get_asset_list_item(elem)
            li.setProperty('IsPlayable', 'true')
            url = plugin.url_for(play, videoid='%s-VIRTUAL|-1' % elem['assetId'])
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

        if len(elems) == limit:
            control_next = { 'en_US' : 'Next', 'uk_UA' : 'Наступна', 'ru_RU' : 'Следующая' }
            li = xbmcgui.ListItem(label=control_next[locale])
            icon = service.addon.getAddonInfo('path') + '/resources/images/next.png'
            li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
            args['offset'] = offset + len(elems)
            url = plugin.url_for(show_series, asset_id=asset_id, season=season)
            url += '?{}'.format(urlencode(args, doseq=True))
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, cacheToDisc=True)

@plugin.route('/search')
def search():
    loc_str = service.addon.getLocalizedString(30525) # 'Input search query'
    query = xbmcgui.Dialog().input(loc_str)
    if query == '':
        return

    url = plugin.url_for(do_search, query=query)
    xbmc.executebuiltin('Container.Update("%s", "replace")' % url)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)

@plugin.route('/search/<query>')
def do_search(query):
    session_id = service.addon.getSetting('session_id')
    elems = service.request.get_search(session_id, query)
    for elem in elems:
        if elem['assetType'] != 'MOVIE' and elem['assetType'] != 'SERIES':
            continue
        li = get_asset_list_item(elem)
        if elem['assetType'] == 'SERIES':
            li.setProperty('IsPlayable', 'false')
            url = plugin.url_for(show_series, asset_id=elem['assetId'], season=0)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        else:
            li.setProperty('IsPlayable', 'true')
            url = plugin.url_for(play, videoid='%s-VIRTUAL|-1' % elem['assetId'])
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=True)

@plugin.route('/videos/<area>')
def show_videos(area):
    session_id = service.addon.getSetting('session_id')

    if area == 'None':
        area = None

    query = ''
    if len(sys.argv) > 2:
        query = sys.argv[2][1:]
    args = parse_qs(query)

    compilation = args.get('compilation', [None])[0]
    if 'filters' not in args:
        args['filters'] = []
    filters = args['filters']
    sort = args.get('sort', [None])[0]
    offset = int(args.get('offset', [0])[0])
    limit = int(args.get('limit', [20])[0])
    select = args.get('select', [None])[0]

    sort_name = args.get('sort_name', [''])[0]
    compilation_name = args.get('compilation_name', [''])[0]

    locale = service.addon.getSetting('locale')
    controls = {
        'filters' : { 'en_US' : 'Filters', 'uk_UA' : 'Фільтри', 'ru_RU' : 'Фильтры', 'icon' : '/resources/images/filters.png' },
        'compilations' : { 'en_US' : 'Selections', 'uk_UA' : 'Підбірки', 'ru_RU' : 'Подборки', 'icon' : '/resources/images/compilations.png' },
        'sort' : { 'en_US' : 'Sorting', 'uk_UA' : 'Сортування', 'ru_RU' : 'Cортировка', 'icon' : '/resources/images/sort.png' },
        }

    if select == 'filters':
        filter_types = service.request.get_content_area_filters(session_id, area)

        filter_names = []
        for filter_type in filter_types:
            names = [i['displayName'] for i in filter_type['filterElements'] if i['id'] in filters]
            filter_names.append('%s (%s)' % (filter_type['displayName'], ', '.join(names)))
        heading = controls[select][locale]
        index = xbmcgui.Dialog().select(heading, filter_names)
        if index < 0:
            return

        filter_type = filter_types[index]
        heading = filter_type['displayName']
        preselect = []
        elems = []
        names = []
        for i in filter_type['filterElements']:
            if i['discriminator'] == 'TagsFilterElementEntity':
                continue
            names.append(i['displayName'])
            elems.append(i)
            if i['id'] in filters:
                preselect.append(len(elems) - 1)
        indexes = []
        if filter_type['multiSelectionEnabled']:
            indexes = xbmcgui.Dialog().multiselect(heading, names, 0, preselect)
        else:
            index = xbmcgui.Dialog().select(heading, names, 0, preselect[0] if len(preselect) > 0 else -1)
            indexes = [index] if index >= 0 else None
        if indexes is None:
            return
        if indexes == preselect:
            return

        for index, elem in enumerate(elems):
            if index in indexes and elem['id'] not in filters:
                args['filters'].append(elem['id'])
            elif index not in indexes and elem['id'] in filters:
                args['filters'].remove(elem['id'])
        del args['select']
        url = plugin.url_for(show_videos, area=area)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmc.executebuiltin('Container.Update("%s")' % url)

    elif select == 'compilations':
        compilations = service.request.get_compilations(session_id, area)
        compilations = [i for i in compilations if i['compilationElementType'] != 'CONTENT_GROUP']

        names = [i['displayName'] for i in compilations]
        heading = controls[select][locale]
        index = xbmcgui.Dialog().select(heading, names)
        if index < 0:
            return

        args['compilation'] = compilations[index]['id']
        args['compilation_name'] = names[index]
        del args['select']
        url = plugin.url_for(show_videos, area=area)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmc.executebuiltin('Container.Update("%s")' % url)

    elif select == 'sort':
        sort_filters = service.request.get_sort_filters(session_id)

        names = [i['displayName'] for i in sort_filters]
        heading = controls[select][locale]
        index = xbmcgui.Dialog().select(heading, names)
        if index < 0:
            return

        args['sort'] = sort_filters[index]['id']
        args['sort_name'] = names[index]
        del args['select']
        url = plugin.url_for(show_videos, area=area)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmc.executebuiltin('Container.Update("%s")' % url)

    if offset == 0:
        for key in controls:
            loc_str = controls[key][locale]
            if key == 'filters' and len(args['filters']) > 0:
                loc_str += ' (%s)' % len(args['filters'])
            elif key == 'compilations' and compilation is not None:
                loc_str += ' (%s)' % compilation_name
            elif key == 'sort' and sort is not None:
                loc_str += ' (%s)' % sort_name
            li = xbmcgui.ListItem(label=loc_str)
            icon = service.addon.getAddonInfo('path') + controls[key]['icon']
            li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
            args['select'] = key
            url = plugin.url_for(show_videos, area=area)
            url += '?{}'.format(urlencode(args, doseq=True))
            del args['select']
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    elems = service.request.get_content_area_elems(session_id, compilation, filters, sort, offset, limit)
    for elem in elems:
        li = get_asset_list_item(elem)
        if elem['assetType'] == 'SERIES':
            li.setProperty('IsPlayable', 'false')
            url = plugin.url_for(show_series, asset_id=elem['assetId'], season=0)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        else:
            li.setProperty('IsPlayable', 'true')
            url = plugin.url_for(play, videoid='%s-VIRTUAL|-1' % elem['assetId'])
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    if len(elems) == limit:
        control_next = { 'en_US' : 'Next', 'uk_UA' : 'Наступна', 'ru_RU' : 'Следующая' }
        li = xbmcgui.ListItem(label=control_next[locale])
        icon = service.addon.getAddonInfo('path') + '/resources/images/next.png'
        li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
        args['offset'] = offset + len(elems)
        url = plugin.url_for(show_videos, area=area)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=True)

@plugin.route('/channel_archive')
def show_archive():
    query = ''
    if len(sys.argv) > 2:
        query = sys.argv[2][1:]
    args = parse_qs(query)

    if 'filters' not in args:
        args['filters'] = []
    filters = args['filters']
    if 'sort' not in args:
        args['sort'] = ['name']
    sort = args['sort'][0]
    if 'order' not in args:
        args['order'] = ['asc']
    sort_order = args['order'][0]
    offset = int(args.get('offset', [0])[0])
    limit = int(args.get('limit', [20])[0])
    select = args.get('select', [None])[0]

    locale = service.addon.getSetting('locale')
    controls = {
        'filters' : { 'en_US' : 'Filters', 'uk_UA' : 'Фільтри', 'ru_RU' : 'Фильтры', 'icon' : '/resources/images/filters.png' },
        'sort' : { 'en_US' : 'Sorting', 'uk_UA' : 'Сортування', 'ru_RU' : 'Cортировка', 'icon' : '/resources/images/sort.png' },
        'channels' : { 'en_US' : 'Channels', 'uk_UA' : 'Канали', 'ru_RU' : 'Каналы', 'icon' : '/resources/images/channels.png' },
        }

    filter_types = {
        'text' : { 'en_US' : 'Text', 'uk_UA' : 'Текст', 'ru_RU' : 'Текст' },
        'genre' : { 'en_US' : 'Genre', 'uk_UA' : 'Жанр', 'ru_RU' : 'Жанр' },
        'year' : { 'en_US' : 'Year', 'uk_UA' : 'Рік', 'ru_RU' : 'Год' },
        'duration' : { 'en_US' : 'Duration', 'uk_UA' : 'Тривалість', 'ru_RU' : 'Продолжительность' },
        'channel' : { 'en_US' : 'Channel', 'uk_UA' : 'Канал', 'ru_RU' : 'Канал' },
    }

    sort_types = {
        'name' : { 'en_US' : 'By name', 'uk_UA' : 'За назвою', 'ru_RU' : 'По названию' },
        'release_date' : { 'en_US' : 'By release date', 'uk_UA' : 'За датою виходу', 'ru_RU' : 'По дате выхода' },
        'duration' : { 'en_US' : 'By duration', 'uk_UA' : 'За тривалістю', 'ru_RU' : 'По продолжительности' },
        'channel_id' : { 'en_US' : 'By channel', 'uk_UA' : 'За каналом', 'ru_RU' : 'По каналу' },
    }

    sort_order_types = {
        'asc' : { 'en_US' : 'Ascending', 'uk_UA' : 'За зростанням', 'ru_RU' : 'По возрастанию' },
        'desc' : { 'en_US' : 'Descending', 'uk_UA' : 'За спаданням', 'ru_RU' : 'По убыванию' },
    }

    if select == 'filters':
        filter_type_ids = list(filter_types.keys())
        filter_type_counts = {id : 0 for id in filter_type_ids}
        for filter in filters:
            filter_type = filter.split(':', 1)[0]
            filter_type_counts[filter_type] += 1
        names = [filter_types[id][locale] + (' (%s)' % filter_type_counts[id] if filter_type_counts[id] > 0 else '') for id in filter_type_ids]

        heading = controls[select][locale]
        index = xbmcgui.Dialog().select(heading, names)
        if index < 0:
            return

        filter_type = filter_type_ids[index]
        elems = service.request.local_get_archive_filters(filter_type)

        heading = filter_types[filter_type][locale]
        preselect = []
        names = []
        if filter_type == 'text':
            add_text_filter = { 'en_US' : 'Add text filter', 'uk_UA' : 'Додати текстовий фільтр', 'ru_RU' : 'Добавить текстовый фильтр' }
            names.append(add_text_filter[locale])
            reset_text_filter = { 'en_US' : 'Reset text filters', 'uk_UA' : 'Скинути текстові фільтри', 'ru_RU' : 'Сбросить текстовые фильтры' }
            names.append(reset_text_filter[locale])
            if 'text:reset_filters' in filters:
                preselect.append(1)
        if filter_type == 'channel':
            channels = service.get_enabled_channels()
            channels = {channel.id: channel.name for channel in channels}
        for elem in elems:
            if filter_type == 'channel':
                names.append(channels[elem])
            elif filter_type == 'year':
                names.append(str(elem))
            else:
                names.append(elem)
            if f'{filter_type}:{elem}' in filters:
                preselect.append(len(names) - 1)
        indexes = xbmcgui.Dialog().multiselect(heading, names, 0, preselect)
        if indexes is None:
            return
        if indexes == preselect:
            return

        if filter_type == 'text':
            if 0 in indexes:
                text = xbmcgui.Dialog().input(heading)
                if text != '':
                    args['filters'].append(f'text:{text}')
            if 1 in indexes:
                args['filters'].append('text:reset_filters')
                indexes = []
            elif 1 in preselect:
                args['filters'].remove('text:reset_filters')
            indexes = [i - 2 for i in indexes if i > 1]

        for index, elem in enumerate(elems):
            filter_elem = f'{filter_type}:{elem}'
            if index in indexes and filter_elem not in filters:
                args['filters'].append(filter_elem)
            elif index not in indexes and filter_elem in filters:
                args['filters'].remove(filter_elem)
        del args['select']
        url = plugin.url_for(show_archive)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmc.executebuiltin('Container.Update("%s")' % url)

    elif select == 'sort':
        sort_type_ids = list(sort_types.keys())
        names = [sort_types[id][locale] for id in sort_type_ids]
        names.append(sort_order_types[sort_order][locale])
        heading = controls[select][locale]
        preselect = sort_type_ids.index(sort)
        index = xbmcgui.Dialog().select(heading, names, 0, preselect)
        if index < 0:
            return
        if index == preselect:
            return

        if index < len(sort_type_ids):
            args['sort'] = sort_type_ids[index]
        else:
            args['order'] = 'desc' if sort_order == 'asc' else 'asc'

        del args['select']
        url = plugin.url_for(show_archive)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmc.executebuiltin('Container.Update("%s")' % url)

    elif select == 'channels':
        channels = service.get_enabled_channels()
        activated_channel_ids = set(service.request.local_get_archive_channels())

        names = []
        preselect = []
        for index, channel in enumerate(channels):
            names.append(channel.name)
            if channel.id in activated_channel_ids:
                preselect.append(index)
        heading = controls[select][locale]
        indexes = xbmcgui.Dialog().multiselect(heading, names, 0, preselect)
        if indexes is None:
            return
        if indexes == preselect:
            return

        selected_channel_ids = [channels[i].id for i in indexes]
        service.request.local_set_archive_channels(urlencode({'channels': selected_channel_ids}, doseq=True))

        del args['select']
        url = plugin.url_for(show_archive)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmc.executebuiltin('Container.Update("%s")' % url)

    if offset == 0:
        for key in controls:
            loc_str = '%s'
            if key == 'filters' and len(filters) > 0:
                loc_str += ' (%s)' % len(filters)
            elif key == 'sort':
                loc_str += ' (%s, %s)' % (sort_types[sort][locale], sort_order_types[sort_order][locale])
            li = xbmcgui.ListItem(label=loc_str % controls[key][locale])
            icon = service.addon.getAddonInfo('path') + controls[key]['icon']
            li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
            args['select'] = key
            url = plugin.url_for(show_archive)
            url += '?{}'.format(urlencode(args, doseq=True))
            del args['select']
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    elems = service.request.local_get_archive(urlencode(args, doseq=True))
    for elem in elems:
        li = get_asset_list_item(elem)
        li.setProperty('IsPlayable', 'true')
        url = plugin.url_for(play_archive, program_asset_id=elem['program_asset_id'])
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    if len(elems) == limit:
        control_next = { 'en_US' : 'Next', 'uk_UA' : 'Наступна', 'ru_RU' : 'Следующая' }
        li = xbmcgui.ListItem(label=control_next[locale])
        icon = service.addon.getAddonInfo('path') + '/resources/images/next.png'
        li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
        args['offset'] = offset + len(elems)
        url = plugin.url_for(show_archive)
        url += '?{}'.format(urlencode(args, doseq=True))
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=True)

@plugin.route('/reset_archive')
def reset_archive():
    loc_str_1 = service.addon.getLocalizedString(30119) # 'Resetting the archive database'
    loc_str_2 = service.addon.getLocalizedString(30120) # 'Are you sure you want to reset the archive database?'
    loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
    loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
    result = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
    if not result:
        return

    service.request.local_reset_archive()

@plugin.route('/channel_manager')
def show_channel_manager():
    channels = service.request.local_get_channels()

    loc_str = service.addon.getLocalizedString(30501) # 'Disabled'
    li = xbmcgui.ListItem(label='%s (%s)' % (loc_str, len(channels['disabled'])))
    icon = service.addon.getAddonInfo('path') + '/resources/images/disabled-list.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_dir, category='disabled')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    loc_str = service.addon.getLocalizedString(30502) # 'New'
    li = xbmcgui.ListItem(label='%s (%s)' % (loc_str, len(channels['new'])))
    icon = service.addon.getAddonInfo('path') + '/resources/images/new-list.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_dir, category='new')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    loc_str = service.addon.getLocalizedString(30503) # 'Removed'
    li = xbmcgui.ListItem(label='%s (%s)' % (loc_str, len(channels['removed'])))
    icon = service.addon.getAddonInfo('path') + '/resources/images/removed-list.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_dir, category='removed')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    loc_str = service.addon.getLocalizedString(30504) # 'Update from Kyivstar TV'
    li = xbmcgui.ListItem(label=loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/update-from-remote.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(send_command, command='download')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    if service.save_manager.m3u_path is not None:
        loc_str = service.addon.getLocalizedString(30505) # 'Load from file'
        li = xbmcgui.ListItem(label=loc_str)
        icon = service.addon.getAddonInfo('path') + '/resources/images/load-from-file.png'
        li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
        command = 'load'
        if channels['changed']:
            command = 'load_changed'
        url = plugin.url_for(send_command, command=command)
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

        format_str = '{}'
        if channels['changed']:
            format_str = '[COLOR=gold]*{}[/COLOR]'
        loc_str = service.addon.getLocalizedString(30506) # 'Save to file'
        li = xbmcgui.ListItem(label=format_str.format(loc_str))
        icon = service.addon.getAddonInfo('path') + '/resources/images/save-to-file.png'
        li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
        url = plugin.url_for(send_command, command='save')
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    for channel in channels['enabled']:
        li = xbmcgui.ListItem(label=channel['name'])
        li.setArt({'icon': channel['logo'], 'fanart': service.addon.getAddonInfo('fanart')})
        url = plugin.url_for(show_channel, asset=channel['id'])
        url += '?movable'
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)

@plugin.route('/channel_manager/dir/<category>')
def show_dir(category):
    channels = service.request.local_get_channels()

    for channel in channels[category]:
        li = xbmcgui.ListItem(label=channel['name'])
        li.setArt({'icon': channel['logo'], 'fanart': service.addon.getAddonInfo('fanart')})
        url = plugin.url_for(show_channel, asset=channel['id'])
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)

@plugin.route('/channel_manager/command/<command>')
def send_command(command):
    if command == 'load_changed':
        loc_str_1 = service.addon.getLocalizedString(30116) # 'Loading from file'
        loc_str_2 = service.addon.getLocalizedString(30117) # 'You have unsaved changes. If you proceed, you will lose it. Continue?'
        loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
        loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
        result = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
        if not result:
            return
        command = 'load'

    service.request.local_execute(command)
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/channel_manager/channel/<asset>')
def show_channel(asset):
    channel = service.request.local_get_channel(asset)

    loc_str = service.addon.getLocalizedString(30507) # 'Preview'
    li = xbmcgui.ListItem(label=loc_str)
    li.setProperty('IsPlayable', 'true')
    icon = service.addon.getAddonInfo('path') + '/resources/images/preview.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(play, videoid='%s-%s|null' % (channel['id'], channel['type']))
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    loc_str = service.addon.getLocalizedString(30508) # 'Enabled'
    if not channel['enabled']:
        loc_str = service.addon.getLocalizedString(30509) # 'Disabled'
    li = xbmcgui.ListItem(label=loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/enabled.png'
    if not channel['enabled']:
        icon = service.addon.getAddonInfo('path') + '/resources/images/disabled.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='enabled')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    loc_str = service.addon.getLocalizedString(30510) # 'Name'
    li = xbmcgui.ListItem(label='%s (%s)' % (loc_str, channel['name']))
    icon = service.addon.getAddonInfo('path') + '/resources/images/name.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='name')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    loc_str = service.addon.getLocalizedString(30511) # 'Logo'
    li = xbmcgui.ListItem(label='%s (%s)' % (loc_str, channel['logo']))
    li.setArt({'icon': channel['logo'], 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='logo')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    loc_str = service.addon.getLocalizedString(30515) # 'Number'
    li = xbmcgui.ListItem(label='%s (%s)' % (loc_str, channel['chno']))
    icon = service.addon.getAddonInfo('path') + '/resources/images/chno.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='chno')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    movable = len(sys.argv) >= 3 and sys.argv[2] == '?movable'
    if movable:
        loc_str = service.addon.getLocalizedString(30514) # 'Move'
        li = xbmcgui.ListItem(label=loc_str)
        icon = service.addon.getAddonInfo('path') + '/resources/images/move.png'
        li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
        url = plugin.url_for(update_channel, asset=channel['id'], _property='move')
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    groups = ';'.join(channel['groups'])
    loc_str = service.addon.getLocalizedString(30517) # 'Include/exclude groups'
    li = xbmcgui.ListItem(label='%s (%s)' % (loc_str, groups))
    icon = service.addon.getAddonInfo('path') + '/resources/images/group-include-exclude.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='groups')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    loc_str = service.addon.getLocalizedString(30518) # 'Rename group'
    li = xbmcgui.ListItem(label=loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/group-rename.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='rename_group')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    loc_str = service.addon.getLocalizedString(30519) # 'Create new group'
    li = xbmcgui.ListItem(label=loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/group-create.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='create_group')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    loc_str = service.addon.getLocalizedString(30520) # 'Remove chosen groups'
    li = xbmcgui.ListItem(label=loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/group-remove.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(update_channel, asset=channel['id'], _property='remove_groups')
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)

@plugin.route('/channel_manager/channel/<asset>/<_property>')
def update_channel(asset, _property):
    if _property == 'move':
        channels = service.request.local_get_channels()
        position = 0
        for channel in channels['enabled']:
            if channel['id'] == asset:
                continue
            li = xbmcgui.ListItem(label=channel['name'])
            li.setArt({'icon': channel['logo'], 'fanart': service.addon.getAddonInfo('fanart')})
            url = plugin.url_for(move_channel, asset=asset, position=position)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=False)
            position += 1

        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    channel = service.request.local_get_channel(asset)

    if _property == 'enabled':
        value = 'unused'
    elif _property == 'name':
        loc_str = service.addon.getLocalizedString(30512) # 'Change channel name'
        value = xbmcgui.Dialog().input(loc_str, defaultt=channel['name'])
        if value == '' or value == channel['name']:
            return
    elif _property == 'logo':
        loc_str = service.addon.getLocalizedString(30513) # 'Change channel logo'
        value = xbmcgui.Dialog().browseSingle(2, loc_str, '', '.jpg|.png', False, False, channel['logo'])
        if value == '' or value == channel['logo']:
            return
    elif _property == 'chno':
        loc_str = service.addon.getLocalizedString(30516) # 'Change channel number'
        value = xbmcgui.Dialog().input(loc_str, defaultt=channel['chno'], type=1)
        if value == channel['chno']:
            return
    elif _property == 'groups':
        all_groups = channel['all_groups']
        groups = channel['groups']
        preselect = [index for index, value in enumerate(all_groups) if value in groups]
        loc_str = service.addon.getLocalizedString(30517) # 'Include/exclude groups'
        indexes = xbmcgui.Dialog().multiselect(loc_str, all_groups, 0, preselect)
        if indexes is None:
            return
        values = [value for index, value in enumerate(all_groups) if index in indexes]
        if groups == values:
            return
        value = ';'.join(values)
    elif _property == 'rename_group':
        all_groups = channel['all_groups']
        loc_str = service.addon.getLocalizedString(30518) # 'Rename group'
        index = xbmcgui.Dialog().select(loc_str, all_groups)
        if index < 0:
            return
        old_value = all_groups[index]
        new_value = xbmcgui.Dialog().input(loc_str, defaultt=old_value)
        if new_value == '' or new_value == old_value:
            return
        value = '%s;%s' % (old_value, new_value)
    elif _property == 'create_group':
        loc_str = service.addon.getLocalizedString(30519) # 'Create new group'
        value = xbmcgui.Dialog().input(loc_str, defaultt='')
        if value == '' or value in channel['all_groups']:
            return
    elif _property == 'remove_groups':
        all_groups = channel['all_groups']
        loc_str = service.addon.getLocalizedString(30520) # 'Remove chosen groups'
        indexes = xbmcgui.Dialog().multiselect(loc_str, all_groups)
        if indexes is None:
            return
        values = [value for index, value in enumerate(all_groups) if index in indexes]
        if values == []:
            return
        loc_str_1 = service.addon.getLocalizedString(30114) # 'Warning'
        loc_str_2 = service.addon.getLocalizedString(30118) # 'It will remove chosen groups from all channels. Continue?'
        loc_str_3 = service.addon.getLocalizedString(30112) # 'Yes'
        loc_str_4 = service.addon.getLocalizedString(30113) # 'No'
        result = xbmcgui.Dialog().yesno(loc_str_1, loc_str_2, yeslabel=loc_str_3, nolabel=loc_str_4)
        if not result:
            return
        value = ';'.join(values)

    service.request.local_update_channel(asset, _property, quote(value))
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/channel_manager/move/<asset>/<position>')
def move_channel(asset, position):
    service.request.local_move_channel(asset, position)
    xbmc.executebuiltin('Container.Update("%s", "replace")' % plugin.url_for(show_channel_manager))

@plugin.route('/settings')
def show_settings():
    service.addon.openSettings()

if __name__ == '__main__':
    plugin.run()
