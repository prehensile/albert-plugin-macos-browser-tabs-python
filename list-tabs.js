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

  if (!app.running()) return;

  app.includeStandardAdditions = true;
  let windowCount = app.windows.length;
  let tabsTitle = app.windows.tabs.name();
  let tabsUrl = app.windows.tabs.url();

  let browserPath = getApplicationPath( browserName );
  let iconUrl = "qfip:" + browserPath;

  let includeMinimized, includeHidden = false;
  if(args.length > 1) includeMinimized = (args[1] === 1)
  if(args.length > 2) includeHidden = (args[2] === 1)

  for (let w = 0; w < windowCount; w++) {

    const wdw = app.windows[w];

    const winHidden = !wdw.properties()["visible"];
    const winMinimized = wdw.properties()["miniaturized"];
    
    // skip windows which are not visible, and also not minimised
    // (window list for Orion contains loads of these weird ghost windows)
    if( browserName =="Orion" ){
      if( winHidden && (!winMinimized) )
        continue;
    }

    // if(winHidden && !includeHidden) continue;
    // if(winMinimized && !includeMinimized) continue;

    const wid = wdw.properties()["id"];
    
    for (let t = 0; t < tabsTitle[w].length; t++) {
      
      let url = tabsUrl[w][t] || "";
      let matchUrl = url.replace(/(^\w+:|^)\/\//, "");
      let title = tabsTitle[w][t] || matchUrl;
      
      let item = {
          title,
          url,
          windowId: wid,
          tabIndex: t,
          iconUrl,
          searchString: "",
          browserPath,
          browserName
        };
      console.log(
        JSON.stringify( item )
      )
    }
  }

}
