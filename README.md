# Kyivstar TV plugin for Kodi media player.

Kyivstar TV is an interactive television with legal content from Ukrainian and international TV channels in HD and standard quality, as well as a wide library of movies, TV series, cartoons and shows.

This plugin is based on: https://github.com/david-hazi/plugin.video.sweettv

# Installation:

To get automatic updates you can install my [repository](https://github.com/TVHomeNetwork/kodi.repository).

Or download any release version from [Releases](https://github.com/TVHomeNetwork/plugin.video.kyivstar.tv/releases).

Or to get fresh version, clone this repository as zip. Unpack somwhere. Rename the top directory from *plugin.video.kyivstar.tv-main* to *plugin.video.kyivstar.tv*.
Pack back to zip and install this file in Kodi.

# Setup:

The plugin works only if the user has logged in to his account. If you don't have an account, you can use the free option to watch channels from Kyivstar TV. To do this, you need to log in as anonymous.
 1. After installation, go to *Settings->Add-ons->My add-ons->Video add-ons->Kyivstar TV* and select *Configure*.
 2. In *Account* section, click on *Login* button. You have three options to log in: with phone number(need to input full number, 38xxxxxxxxxx), with personal account(in username field you need specify personal account number) and as anonymous.
 3. In *M3U* section, specify the file name and directory path in which the file will be ctreated.
 4. In *EPG* section, we do the same. You can also specify the time of daily update.
 5. Click OK and plugin will create two files.
It will take more time to create EPG file, because for each channel there are need separate request. Options to contol this process are in *EPG->Save options*.

# Setup IPTV Simple Client

First, you need install it. Go to *Settings->Add-ons->Install from repository->PVR clients->PVR IPTV Simple Client* and press *Install*.
 1. Go to settings *Settings->Add-ons->My add-ons->PVR Clients->IPTV Simple Client*
 2. Select *Add add-on configuration*
 3. In *General* section, set *Name* to 'kyivstar' (or any other), *Location* to 'local path' and in *M3U playlist path* specify path to the file that was created previously.
 4. In *EPG* section, again we do the same.
 5. In *Catchup* section, turn on *Enable Catchup*, turn off *Play from EPG in Live TV mode (using timeshift)*, set *Buffer before program start* and *Buffer after program end* to 0.

[More info about IPTV Simple Client](https://kodi.wiki/view/Add-on:PVR_IPTV_Simple_Client)

