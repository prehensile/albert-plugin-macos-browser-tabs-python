import re
import subprocess
import json
import threading
from dataclasses import dataclass
from typing import List
from pathlib import Path
import time
from urllib.parse import urlparse

from albert import *


md_iid = '3.0'
md_version = '0.3'
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

###
# TODO
# ---
# - work out why the index is empty on the first couple of triggers
# - fetch favicons
#


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
        print(f"Error getting tabs with titles: {e}")
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
    

    def onQuery( self, query ):
        # update index every time a query comes in, with some logic to debounce etc

        now = time.time()
        qs = query.string
        
        if(
            query.isValid and
            (
                ( (self.lastQueryString is None) or ( self.lastQueryString not in qs) ) or
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


    def itemAction( self, ti ):
        self.lastQueryString = None
        switch_to_tab( ti )


    def updateIndexItems(self):
        if self.thread and self.thread.is_alive():
            self.thread.join()
        self.thread = threading.Thread(target=self.update_index_items_worker)
        self.thread.start()

    def update_index_items_worker(self):
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
            
            # update index items atomically
            self.setIndexItems( index_items )


if __name__ == "__main__":
    for tab in get_webkit_tabs( "Orion" ):
        print( tab )