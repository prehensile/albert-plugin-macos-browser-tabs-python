#!/usr/bin/env osascript -l JavaScript

function run(args) {

    const browser = args[0];
    const windowId = args[1];
    const tabIndex = args[2];

    const app = Application( browser );
    const window = app.windows.byId( windowId );
    try {
        // if this succeeds, it's probably a webkit-based browser
        window.currentTab = window.tabs[ tabIndex ];    
    } catch (error) {
        // assume that a fail means it's a chromium-based browser
        // activeTabIndex is 1-indexed
        window.activeTabIndex = parseInt(tabIndex) + 1;
    }
    
    app.activate();
    window.index = 1;
}