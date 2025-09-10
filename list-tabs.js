#!/usr/bin/env osascript -l JavaScript

function getApplicationPath( browserName ) {
  
  let ca = Application.currentApplication();
  ca.includeStandardAdditions = true;
  
  const se = Application('System Events');
  const process = se.processes.byName( browserName );
  const bundleId = process.bundleIdentifier();
  
  const pth = ca.doShellScript(
    `mdfind "kMDItemCFBundleIdentifier == ${bundleId}"`
  )
  
  return pth
}


function run(args) {
  
  let browserName = args[0];
  let app = Application(browserName);

  if (!app.running()) {
    return JSON.stringify({
      items: [
        {
          title: `${browserName} is not running`,
          subtitle: `Press enter to launch ${browserName}`,
        },
      ],
    });
  }

  app.includeStandardAdditions = true;
  let windowCount = app.windows.length;
  let tabsTitle = app.windows.tabs.name();
  let tabsUrl = app.windows.tabs.url();

  let iconUrl = "qfip:" + getApplicationPath( browserName );

  for (let w = 0; w < windowCount; w++) {

    const wdw = app.windows[w];
    
    // skip hidden windows
    // (window list for Orion contains loads of hidden windows which aren't shown in the UI)
    if( !wdw.properties()["visible"] )
      continue;

    const wid = wdw.properties()["id"];
    
    for (let t = 0; t < tabsTitle[w].length; t++) {
      
      let url = tabsUrl[w][t] || "";
      let matchUrl = url.replace(/(^\w+:|^)\/\//, "");
      let title = tabsTitle[w][t] || matchUrl;
      // let searchString = `${title} ${decodeURIComponent(matchUrl).replace(
      //   /[^\w]/g,
      //   " ",
      // )}`;
      
      let item = {
          title: title,
          url: url,
          windowId: wid,
          tabIndex: t,
          iconUrl : iconUrl,
          searchString: "",
        };
      console.log(
        JSON.stringify( item )
      )
    }
  }

}
