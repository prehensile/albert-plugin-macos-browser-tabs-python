import os
import re
import subprocess
import json
import threading
from dataclasses import dataclass
from typing import List
from pathlib import Path
import time
from urllib.parse import urlparse
import logging

from albert import *


md_iid = '3.0'
md_version = '0.4'
md_name = 'Browser Tabs (macOS)'
md_description = 'Lists open tabs in browsers on macOS'
md_url = "https://github.com/prehensile/albert-plugin-tabs-python"
md_license = "WTFPL"
md_authors = ["@prehensile"]
md_maintainers = ["@prehensile"]


###
# CHANGELOG
# ---
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


###
# TODO
# ---
# - fetch favicons
# - clever diffing on index rebuild so that we only update what's changed


list_js = Path(__file__).parent / "list-tabs.js"
focus_js = Path(__file__).parent / 'focus-tab.js'

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
    if level is None:
        handler = logging.NullHandler()
    else:
        handler = logging.StreamHandler()
        l.setLevel( level )
    l.addHandler(handler)
    return l

_logger:logging.Logger = init_logger(
    os.getenv( "PLUGIN_TABS_LOG_LEVEL" )
)


def get_webkit_tabs( browser ):
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
    
    except subprocess.CalledProcessError as e:
        _logger.error( f"Error getting tabs" )
        _logger.exception( e )
        return []


def switch_to_tab( tab_item:TabItem ):
    subprocess.run([
            focus_js,
            tab_item.browser,
            str(tab_item.window_id),
            str(tab_item.tab_index)
        ],
        check=True
    )


debounce_time = 5.0 # seconds

class Plugin( PluginInstance, IndexQueryHandler ):

    def __init__(self):
        PluginInstance.__init__(self)
        IndexQueryHandler.__init__(self)
        self.thread = None
        self.lastQueryTime = 0
        self.lastQueryString = None
        self.lastIndexItems = []
        self.setIndexItems( self.lastIndexItems )
    

    def onQuery( self, query ):
        # update index every time a query comes in, with some logic to debounce etc

        now = time.time()
        qs = query.string
        
        _logger.debug( "plugin-tabs: onQuery %s %s", qs, query.isValid )

        
        if(
            query.isValid and 
            ( not ( self.thread and self.thread.is_alive() ) ) and
            (
                (
                    (self.lastQueryString is None) or
                    (self.lastQueryString[0] != qs[0]) # probably a whole new query
                ) 
                or
                ( (now - self.lastQueryTime) > debounce_time )
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
        self.lastIndexItems = items
        return super().setIndexItems( items )


    def itemAction( self, ti ):
        self.lastQueryString = None
        switch_to_tab( ti )


    def updateIndexItems(self):
        _logger.debug( "!!plugin-tabs: update_index_items" )
        if self.thread and self.thread.is_alive():
            self.thread.join()
        else:
            self.thread = threading.Thread(target=self.update_index_items_worker)
            self.thread.start()


    def update_index_items_worker(self):

        _logger.debug( "!!!plugin-tabs: update_index_items_worker" )

        index_items = []
        for tab_item in get_webkit_tabs( "Orion" ):
            
            title = tab_item.title
            url = tab_item.url
            
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
            
            parsed_url = urlparse(url)
            search_str = " ".join([
                parsed_url.hostname.replace("www.", "").replace(".", " "),
                title,
                re.sub(r'[^a-zA-Z]', ' ', parsed_url.path)
            ])
            
            # Create searchable string for the item
            index_items.append(
                IndexItem(
                    item = item,
                    string = search_str
                )
            )
            
        _logger.debug( "--> calling setIndexItems with index_items count: %d", len(index_items) )
        self.setIndexItems( index_items )


if __name__ == "__main__":
    for tab in get_webkit_tabs( "Orion" ):
        print( tab )