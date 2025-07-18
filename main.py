import sys
import requests
import routing
import time
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from urllib.parse import quote
from resources.lib.kyivstar_service import KyivstarService

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
    if service.get_session_status() != KyivstarService.SESSION_EMPTY:
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
        service.set_session_status(KyivstarService.SESSION_ACTIVE)
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
        service.set_session_status(KyivstarService.SESSION_ACTIVE)
    else:
        profile = service.request.login(profile['sessionId'], username, password=password)

        if 'userId' not in profile or 'sessionId' not in profile:
            loc_str = service.addon.getLocalizedString(30202) # 'Error during login. Check your logs for details.'
            xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_ERROR)
            return

        service.addon.setSetting('user_id', profile['userId'])
        service.addon.setSetting('session_id', profile['sessionId'])
        service.addon.setSetting('username', username)
        service.addon.getSetting('password', password)
        service.addon.setSetting('logged', 'true')
        service.set_session_status(KyivstarService.SESSION_ACTIVE)

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
        service.set_session_status(KyivstarService.SESSION_INACTIVE)
        return

    service.addon.setSetting('logged', 'false')
    service.addon.setSetting('user_id', '')
    service.addon.setSetting('session_id', '')
    service.set_session_status(KyivstarService.SESSION_EMPTY)

@plugin.route('/play/<videoid>')
def play(videoid):
    if service.get_session_status() == KyivstarService.SESSION_EMPTY:
        loc_str = service.addon.getLocalizedString(30204) # 'Log in to the plugin'
        xbmcgui.Dialog().notification('Kyivstar.tv', loc_str, xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    session_id = service.addon.getSetting('session_id')
    user_id = service.addon.getSetting('user_id')

    videoid, epg = videoid.split('|')
    videoid, video_type = videoid.split('-')
    virtual = video_type=='VIRTUAL'

    epg_str = 'null'
    if epg != 'null':
        epg_int = int(epg)
        epg_str = time.strftime('%Y.%m.%d %H:%M:%S', time.gmtime(epg_int))
        epg_time = epg + '000'

    xbmc.log("KyivstarPlay: asset_id = %s, video_type = %s, epg_time = %s(%s)" % (videoid, video_type, epg, epg_str), xbmc.LOGINFO)

    inputstream = service.addon.getSetting('stream_inputstream')
    url = ''
    if epg == 'null':
        if virtual:
            if service.addon.getSetting('live_stream_server_enabled') == 'true':
                inputstream = service.addon.getSetting('live_stream_inputstream')
                port = int(service.addon.getSetting('live_stream_server_port'))
                url = 'http://127.0.0.1:%s/playlist.m3u8?asset=%s' % (port, videoid)
            else:
                url = service.request.get_elem_stream_url(user_id, session_id, videoid, virtual=virtual)
        else:
            url = service.request.get_elem_stream_url(user_id, session_id, videoid, virtual=virtual)
    else:
        if virtual:
            if service.addon.getSetting('remove_ads_in_catchup_mode') == 'true':
                port = int(service.addon.getSetting('live_stream_server_port'))
                url = 'http://127.0.0.1:%s/playlist.m3u8?asset=%s&epg=%s' % (port, videoid, epg_time)
            else:
                url = service.request.get_elem_stream_url(user_id, session_id, videoid, virtual=virtual, date=epg_time)
        else:
            url = service.request.get_elem_playback_stream_url(user_id, session_id, videoid, epg_time)

    if not url.startswith('http://127.0.0.1'):
        url += '|User-Agent="%s"' % service.request.headers['User-Agent']
        url += '&Referer="%s"' % service.request.headers['Referer']

    xbmc.log("KyivstarPlay: url = %s" % (url), xbmc.LOGINFO)

    play_item = xbmcgui.ListItem(path=url)
    play_item.setMimeType('application/vnd.apple.mpegurl')

    if inputstream != 'default':
        play_item.setProperty('inputstream', inputstream)

    play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')
    play_item.setProperty('inputstream.ffmpegdirect.manifest_type', 'hls')

    if not virtual:
        if epg != 'null':
            #TODO: inputstream.ffmpegdirect need similar option for unfinished catchup
            play_item.setProperty('inputstream.adaptive.play_timeshift_buffer', 'true')
    else:
        if epg == 'null':
            # VIRTUAL channel in live mode return full stream like in VOD mode,
            # so we need to set resume point of video to current time. If we dont
            # do this, video start from the beginning of the file.
            cur_program_epg = service.request.get_elem_cur_program_epg_data(session_id, videoid)
            if 'start' in cur_program_epg and 'finish' in cur_program_epg:
                duration = cur_program_epg['finish']/1000 - cur_program_epg['start']/1000
                live_point = time.time() - cur_program_epg['start']/1000
                video_info = play_item.getVideoInfoTag()
                video_info.setResumePoint(live_point, duration)
    xbmcplugin.setResolvedUrl(handle, True, listitem=play_item)

@plugin.route('')
def root():
    loc_str = service.addon.getLocalizedString(30500) # 'Channel manager'
    li = xbmcgui.ListItem(label='[B]%s[/B]' % loc_str)
    icon = service.addon.getAddonInfo('path') + '/resources/images/channel-manager.png'
    li.setArt({'icon': icon, 'fanart': service.addon.getAddonInfo('fanart')})
    url = plugin.url_for(show_channel_manager)
    xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(handle, cacheToDisc=True)

@plugin.route('/channel_manager')
def show_channel_manager():
    port = service.addon.getSetting('live_stream_server_port')
    url = 'http://127.0.0.1:%s/get_channels' % port
    response = requests.get(url)
    channels = response.json()

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

    if service.m3u_file_path:
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
    port = service.addon.getSetting('live_stream_server_port')
    url = 'http://127.0.0.1:%s/get_channels' % port
    response = requests.get(url)
    channels = response.json()

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

    port = service.addon.getSetting('live_stream_server_port')
    url = 'http://127.0.0.1:%s/execute?command=%s' % (port, command)

    requests.get(url)

    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/channel_manager/channel/<asset>')
def show_channel(asset):
    port = service.addon.getSetting('live_stream_server_port')
    url = 'http://127.0.0.1:%s/get_channel?asset=%s' % (port, asset)
    response = requests.get(url)
    channel = response.json()

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
    port = service.addon.getSetting('live_stream_server_port')
    if _property == 'move':
        url = 'http://127.0.0.1:%s/get_channels' % port
        response = requests.get(url)
        channels = response.json()

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

    url = 'http://127.0.0.1:%s/get_channel?asset=%s' % (port, asset)
    response = requests.get(url)
    channel = response.json()

    url = 'http://127.0.0.1:%s/update_channel?asset=%s&property=%s&value=' % (port, asset, _property)

    if _property == 'enabled':
        url += 'unused'
    elif _property == 'name':
        loc_str = service.addon.getLocalizedString(30512) # 'Change channel name'
        value = xbmcgui.Dialog().input(loc_str, defaultt=channel['name'])
        if value == '' or value == channel['name']:
            return
        url += quote(value)
    elif _property == 'logo':
        loc_str = service.addon.getLocalizedString(30513) # 'Change channel logo'
        value = xbmcgui.Dialog().browseSingle(2, loc_str, '', '.jpg|.png', False, False, channel['logo'])
        if value == '' or value == channel['logo']:
            return
        url += quote(value)
    elif _property == 'chno':
        loc_str = service.addon.getLocalizedString(30516) # 'Change channel number'
        value = xbmcgui.Dialog().input(loc_str, defaultt=channel['chno'], type=1)
        if value == channel['chno']:
            return
        url += quote(value)
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
        url += quote(';'.join(values))
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
        url += quote('%s;%s' % (old_value, new_value))
    elif _property == 'create_group':
        loc_str = service.addon.getLocalizedString(30519) # 'Create new group'
        value = xbmcgui.Dialog().input(loc_str, defaultt='')
        if value == '' or value in channel['all_groups']:
            return
        url += quote(value)
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
        url += quote(';'.join(values))

    requests.get(url)

    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/channel_manager/move/<asset>/<position>')
def move_channel(asset, position):
    port = service.addon.getSetting('live_stream_server_port')
    url = 'http://127.0.0.1:%s/move_channel?asset=%s&position=%s' % (port, asset, position)

    requests.get(url)

    path = 'plugin://%s/channel_manager' % service.addon.getAddonInfo('id')
    xbmc.executebuiltin('Container.Update("%s", "replace")' % path)

if __name__ == '__main__':
    plugin.run()
