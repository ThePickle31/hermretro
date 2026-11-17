// The page's artwork; tools/bundle/bundle.mjs turns each PNG import into a data URL. Most images are 1-bit
// PNGs drawn through a CSS mask in the theme's accent colour, so each skin recolours them (the Hermes
// bust, the flying Chromatic's body and wing). The cartridge is the one full-colour image: the Games
// shelf shows it as a normal background.
import cart from './cart-hermretro.png'
import chromBody from './chrom-body.png'
import chromWing from './chrom-wing.png'
import hermes from './hermes.png'

export const ART_DATA = { hermes, cart, chromBody, chromWing }
