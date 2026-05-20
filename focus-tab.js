#!/usr/bin/env osascript -l JavaScript

function run(args) {

    console.log( "focus-tab args:", JSON.stringify(args) );

    const browser = args[0];
    const windowId = parseInt(args[1]);
    const tabIndex = parseInt(args[2]);
    const targetUrl = args[3];

    if( !browser || isNaN(windowId) || isNaN(tabIndex) || !targetUrl ){
        console.log( `focus-tab: invalid args — browser=${browser}, windowId=${args[1]}, tabIndex=${args[2]}, targetUrl=${targetUrl}` );
        return;
    }

    const isWebkit = (
        browser === "Safari" ||
        browser === "Orion"
    );

    let app;
    try {
        app = Application( browser );
    } catch (error) {
        console.log( `focus-tab: failed to get Application(${browser}): ${error}` );
        return;
    }

    let window = null;
    try {
        window = app.windows.byId( windowId );
        // touch a property to verify the reference is live
        window.id();
    } catch (error) {
        console.log( `focus-tab: window byId(${windowId}) not found in ${browser}: ${error}` );
        window = null;
    }

    let success = false;

    if( window ){
        try {
            if( isWebkit ){
                window.currentTab = window.tabs[ tabIndex ];
                success = window.currentTab.url() == targetUrl;
            } else {
                // chromium-based, activeTabIndex is 1-indexed
                window.activeTabIndex = tabIndex + 1;
                success = window.activeTab.url() == targetUrl;
            }
            if( !success ){
                console.log( `focus-tab: fast path mismatched url at ${browser} window=${windowId} tabIndex=${tabIndex}` );
            }
        } catch (error) {
            console.log( `focus-tab: fast path failed (${browser}, isWebkit=${isWebkit}, windowId=${windowId}, tabIndex=${tabIndex}): ${error}` );
        }
    }

    if( !success ) {

        // fall back to scanning every window/tab for a matching url
        // slower, but more likely to work
        console.log( `focus-tab: falling back to full scan for ${targetUrl}` );

        let windows = [];
        try {
            windows = app.windows();
        } catch (error) {
            console.log( `focus-tab: app.windows() failed for ${browser}: ${error}` );
            return;
        }

        for (const w of windows ) {
            let tabs = [];
            try {
                tabs = w.tabs();
            } catch (error) {
                console.log( `focus-tab: w.tabs() failed, skipping window: ${error}` );
                continue;
            }
            for (let i = 0; i < tabs.length; i++ ) {
                let tabUrl;
                try {
                    tabUrl = tabs[i].url();
                } catch (error) {
                    // some tabs (e.g. PWAs / blank tabs) refuse to give a url
                    continue;
                }
                if( tabUrl == targetUrl ){
                    try {
                        if( isWebkit ) w.currentTab = tabs[i];
                        else w.activeTabIndex = i + 1;
                        window = w;
                        success = true;
                    } catch (error) {
                        console.log( `focus-tab: failed to activate matched tab in ${browser}: ${error}` );
                    }
                    break;
                }
            }
            if( success ) break;
        }

        if( !success ){
            console.log( `focus-tab: no tab matching ${targetUrl} found in any ${browser} window` );
        }
    }

    // bring app and window to foreground
    try {
        app.activate();
    } catch (error) {
        console.log( `focus-tab: app.activate() failed: ${error}` );
    }

    if( window ){
        try {
            window.index = 1;
        } catch (error) {
            console.log( `focus-tab: setting window.index=1 failed: ${error}` );
        }
    }

    if( success ){
        console.log( `focus-tab: focused ${targetUrl} in ${browser}` );
    }
}
