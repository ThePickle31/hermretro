// Home: the front door of the page (its descriptor; fields in app/registry.js). Nothing else uses Home.
import { HOME_CSS } from './home.css.js'
import { Home } from './home-page.js'

export const HOME_PAGE = {
  id: 'home',
  label: 'Home',
  Page: Home,
  css: [HOME_CSS]
}
