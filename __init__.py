import os
import re
import subprocess
import json
import sys
import threading
from dataclasses import dataclass
from typing import List
from pathlib import Path
import time
from urllib.parse import urlparse
import logging

from albert import *


md_iid = '3.0'
md_version = '0.7'
md_name = 'Browser Tabs (macOS)'
md_description = 'Lists and focuses open tabs in Webkit and Chromium based browsers on macOS'
md_url = "https://github.com/prehensile/albert-plugin-macos-browser-tabs-python"
md_license = "MIT"
md_authors = ["@prehensile"]
md_maintainers = ["@prehensile"]
md_platforms = ["Darwin"]


###
# CHANGELOG
# ---
#
# 0.2
# - call updateIndexItems whenever the plugin is triggered
# - take searchString from list-tabs.js and pass it to IndexItem
#
# 0.3
# - improved IndexItem lookup string
# 
# 0.4
# - Added sensible logging
# - Improved empty index on early triggers and logic around when updateIndexItems happens
#
# 0.5
# - Removed hidden windows from index (amend to list-tabs.js)
# - Tweaked index string generation
# - Dedupe items
#
# 0.6
# - Tested on Safari, Orion, and Chromium
# - Tidied / slightly refactored list-tabs.js
# - Amended hidden windows logic to include minimized windows
# - Fixed an issue where urls without a hostname caused update_index_items_worker to crash
#
# 0.7
# - Support for multiple concurrent browsers
# - Added config widgets
# - Tested on Brave, Vivaldi and Edge
#
# 0.71
# - Fixed an exception where list-tabs.js doesn't return anything
# - Added README
#  
# 0.72
# - Added a loading item to display while tabs are being indexed
#

###
# TODO
# ---
# - fetch favicons
# --> from e.g /Users/prehensile/Library/Caches/com.kagi.kagimacOS.IconService
# - clever diffing on index rebuild so that we only update what's changed and do it more quickly / atomically
# --> e.g do atomic updates per-window
#

list_js = Path(__file__).parent / "list-tabs.js"
focus_js = Path(__file__).parent / 'focus-tab.js'

_debounce_time = 60.0 # seconds

_supported_browsers = [
    ("Safari", "Webkit"),
    ("Orion", "Webkit"),
    ("Chrome", "Chromium"), 
    ("Chromium", "Chromium"),
    ("Brave", "Chromium"),
    ("Vivaldi", "Chromium"),
    ("Edge", "Chromium")
]

@dataclass
class TabItem:
    browser: str
    title: str
    url : str
    tab_index : int
    window_id : int
    url_icon : str
    search_string : str


def init_logger( level=None ):
    
    l = logging.getLogger('plugin-tabs')
    handler = None

    if level is None:
        handler = logging.NullHandler()
    else:
        handler = logging.StreamHandler()
        l.setLevel( level )
        formatter = logging.Formatter(
            fmt = "%(asctime)s [%(levelname)s:%(name)s] %(message)s",
            datefmt = "%H:%M:%S"
        )
        handler.setFormatter(formatter)

    l.addHandler(handler)
    return l


_logger:logging.Logger = init_logger(
    os.getenv( "PLUGIN_TABS_LOG_LEVEL" )
)


def get_browser_tabs( browser ):
    """
    Get URLs and titles of all webkit tabs.
    Yields a list of TabItems
    """
    
    try:
        proc = subprocess.Popen(
            [ list_js, browser ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        for line in proc.stderr:
            if line and len(line) > 0:
                try:
                    j = json.loads( line )
                    ti = TabItem(
                        title = j["title"],
                        url = j["url"],
                        window_id = j["windowId"],
                        tab_index = j["tabIndex"],
                        browser = browser,
                        url_icon = j["iconUrl"],
                        search_string = j["searchString"]
                    )
                    yield ti
                except json.JSONDecodeError as e:
                    _logger.exception( e )
    
    except subprocess.CalledProcessError as e:
        _logger.error( f"Error getting tabs" )
        _logger.exception( e )


def switch_to_tab( tab_item:TabItem ):
    subprocess.run([
            focus_js,
            tab_item.browser,
            str(tab_item.window_id),
            str(tab_item.tab_index)
        ],
        check=True
    )


def loading_item():
    return IndexItem(
        item = StandardItem(
            id = '',
            text = "Browser tabs are being indexed...",
        ),
        string = ""
    )



class Plugin( PluginInstance, IndexQueryHandler ):


    def __init__(self):
        PluginInstance.__init__(self)
        IndexQueryHandler.__init__(self)
        self.lastQueryTime = 0
        self.lastQueryString = None
        self.indexItemsByBrowser = {}
        self.browser_threads = {}
        self.setIndexItems( [] )
        self.load_config()


    def load_config(self):
        for browser, _ in _supported_browsers:
            prop_name = f'prop_{browser}'
            prop = self.readConfig(prop_name, bool)
            v = bool(prop)
            _logger.debug(f"loadConfig:{browser}, {prop}, {v}")
            setattr(self, prop_name, v)


    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        _logger.debug(f"__setattr__: {name}, {value}")
        if name.startswith('prop_'):
            self.writeConfig(name, value)


    def configWidget(self):

        widgets = [{
            "type": "label", 
            "text": "Include tabs from these browsers:"
        }]
        
        current_category = None
        for browser, category in _supported_browsers:
            # if category and category != current_category:
            #     widgets.append({"type": "label", "text": category})
            #     current_category = category
                
            widgets.append({
                "type": "checkbox",
                "property": f"prop_{browser}",
                "label": browser
            })
            
        return widgets


    def onQuery( self, query ):
        # update index every time a query comes in, with some logic to debounce etc

        now = time.time()
        qs = query.string
        
        _logger.debug( "plugin-tabs: onQuery %s %s", qs, query.isValid )
        
        if(
            query.isValid and 
            (
                (
                    (self.lastQueryString is None) or
                    (self.lastQueryString[0] != qs[0]) # probably a whole new query
                ) 
                or
                ( (now - self.lastQueryTime) > _debounce_time )
            )
        ):
            self.updateIndexItems()
        
        self.lastQueryString = qs
        self.lastQueryTime = now


    def handleTriggerQuery(self, query):
        self.onQuery( query )        
        return super().handleTriggerQuery(query)


    def handleGlobalQuery(self, query):
        self.onQuery( query )        
        return super().handleGlobalQuery(query)


    def setIndexItems( self, items ):
        _logger.debug( "setIndexItems with item count: %d", len(items) )
        return super().setIndexItems( items )


    def itemAction( self, ti ):
        self.lastQueryString = None
        switch_to_tab( ti )


    def updateIndexItems( self ):
        
        _logger.debug( "update_index_items" )
        
        if not self.indexItemsByBrowser:
            # index items are currently empty
            self.setIndexItems([loading_item()])
        
        browser_thread = None

        for browser, _ in _supported_browsers:

            # skip browsers turned off in config
            if not getattr(self, f"prop_{browser}" ):
                continue
        
            if browser in self.browser_threads:
            
                browser_thread = self.browser_threads[ browser ]
                if browser_thread and browser_thread.is_alive():
                    # browser_thread.join()
                    return
           
            browser_thread = threading.Thread(
                target = self.update_index_items_worker,
                args = (browser,)
            )
            
            browser_thread.start()
            self.browser_threads[ browser ] = browser_thread


    def setIndexItemsForBrowser( self, browser, index_items ):
        _logger.info( f"setIndexItemsForBrowser: {browser} with {len(index_items)} items" )
        
        self.indexItemsByBrowser[browser] = index_items
        
        all_items = []
        for items in self.indexItemsByBrowser.values():
            all_items.extend( items )
        
        self.setIndexItems( all_items )


    def update_index_items_worker( self, browser ):

        _logger.debug( f"!!! plugin-tabs: update_index_items_worker: {browser}" )
        
        indexed_checkstrings = set()
        index_items = []
        
        for tab_item in get_browser_tabs( browser ):
            
            try:

                title = tab_item.title
                url = tab_item.url

                # skip tabs with duplicate url + title pairs 
                # (sometimes we have multiple tabs with the same url but different titles if they're e.g different views onto the same webapp)
                checkstring = f"{title}{url}"
                if checkstring in indexed_checkstrings:
                    continue
                indexed_checkstrings.add( checkstring )

                item = StandardItem(
                    id = url,
                    text = title if title else url,
                    subtext = "⧉ " + url[ url.find("://") + 3: ],
                    iconUrls = [
                        # TODO: fetch favicon
                        url,
                        tab_item.url_icon
                    ],
                    actions=[
                        Action( "focus", "Focus tab", lambda ti=tab_item: self.itemAction(ti) )
                    ],
                )
                
                _logger.debug( tab_item )

                # Create searchable string for the item
                parsed_url = urlparse(url)
                search_parts = [title]
                # being careful about url parts here, because sometimes they're not there
                if parsed_url.hostname:
                    search_parts.append( parsed_url.hostname.replace("www.", "").replace(".", " ") )
                if parsed_url.path:
                    search_parts.append(
                        re.sub(r'[^a-zA-Z]', ' ', parsed_url.path )
                    )
                search_str = " ".join( search_parts )
                _logger.debug( f"{url}\n\t{search_str}" )
                
                index_items.append(
                    IndexItem(
                        item = item,
                        string = search_str
                    )
                )
            except Exception as e:
                _logger.error( "Exception in update_index_items_worker" )
                _logger.exception( e )
            
        self.setIndexItemsForBrowser( browser, index_items  )


if __name__ == "__main__":
    for tab in get_browser_tabs( sys.argv[1] ):
        print( tab )
