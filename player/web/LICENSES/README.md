# Notices for the bundled demo player

`player/web/` is GB Studio's default browser player (the "Binjgb" web template) so the Studio's
Emulator page can run ModRetro's player before the user has a game of their own.

| Files | Project | Licence |
|---|---|---|
| `index.html`, `css/style.css`, `js/script.js`, `js/debugger.js` | GB Studio web template (`appData/webTemplates/binjgb`), by Chris Maltby and contributors | MIT, `gb-studio-LICENSE.txt` |
| `js/binjgb.js`, `js/binjgb.wasm` | binjgb by Ben Smith, GB Studio's WebAssembly build (`appData/wasm/binjgb`, includes changes from Daid's fork) | MIT, `binjgb-LICENSE.txt` |

`index.html` is the template with its placeholders filled the way GB Studio's web export fills them
(title, author, background colour); `gbstudio.json` holds GB Studio's default controls. The demo ROM
(`hello-color.gbc`) is not copied here: the server reads it from the bundled ModRetro engine's
`examples/hello-color/`.
