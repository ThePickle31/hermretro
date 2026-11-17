// Home: the front door of the page (its descriptor; fields in app/registry.js). Nothing else uses Home.
import { jsx } from '#sdk'
import { HOME_CSS } from './home.css.js'
import { HomePage } from './home-page.js'

function Home({ shell }) {
  return jsx(HomePage, {
    auto: shell.auto,
    autoId: shell.autoId,
    choosing: shell.choosing,
    ctx: shell.ctx,
    doctor: shell.doctor,
    games: shell.games,
    memory: shell.memory,
    onGo: shell.go,
    onOpenPrompt: shell.openPrompt,
    onPlay: shell.play,
    onSetUpDevice: shell.setUpDevice,
    status: shell.status,
    steps: shell.steps
  })
}

export const HOME_PAGE = {
  id: 'home',
  label: 'Home',
  Page: Home,
  css: [HOME_CSS]
}
