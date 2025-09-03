#!/usr/bin/env osascript -l JavaScript

function run(args) {
  
  let browserName = args[0];
  
  if (!Application(browserName).running()) {
    return JSON.stringify({
      items: [
        {
          title: `${browserName} is not running`,
          subtitle: `Press enter to launch ${browserName}`,
        },
      ],
    });
  }

  let getApplicationPath = function(browserName) {
    let app = Application.currentApplication();
    app.includeStandardAdditions = true;
    const se = Application('System Events');
    const process = se.processes.byName( browserName );
    const bundleId = process.bundleIdentifier();
    const script = 'mdfind "kMDItemCFBundleIdentifier == ' + bundleId + '"';
    const pth = app.doShellScript( script )
    return pth
  }

  let app = Application(browserName);
  app.includeStandardAdditions = true;
  let windowCount = app.windows.length;
  let tabsTitle = app.windows.tabs.name();
  let tabsUrl = app.windows.tabs.url();

  let iconUrl = "qfip:" + getApplicationPath( browserName );

  for (let w = 0; w < windowCount; w++) {

    const wid = app.windows[w].properties()["id"];

    for (let t = 0; t < tabsTitle[w].length; t++) {
      let url = tabsUrl[w][t] || "";
      let matchUrl = url.replace(/(^\w+:|^)\/\//, "");
      let title = tabsTitle[w][t] || matchUrl;

       let item = {
          title,
          url,
          windowId: wid,
          tabIndex: t,
          iconUrl : iconUrl,
          match: `${title} ${decodeURIComponent(matchUrl).replace(
            /[^\w]/g,
            " ",
          )}`,
        };

      console.log(
        JSON.stringify( item )
      )

    }
  }

}
