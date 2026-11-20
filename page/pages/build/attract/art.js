// The world's object pixel art at 24-px tiles, one character per pixel ('.' clear); the letters are inks that
// palettes.js maps to colours per sky. Enemies are in art-enemies.js, the Nous Girl in girl.js.

// coin, 12x16, four spin frames (face, three-quarter, edge, three-quarter): K outline, Y gold, y shade, W shine
export const COIN = [
  [
    '....KKKK....',
    '...KYYYYK...',
    '..KYYYYyyK..',
    '.KYYYYYYyyK.',
    'KYYWYYYYYyyK',
    'KYYWYYyYYyyK',
    'KYYWYYyYYyyK',
    'YYYWYYyYYyyy',
    'YYYWYYyYYyyy',
    'KYYWYYyYYyyK',
    'KYYWYYyYYyyK',
    'KYYWYYYYyyyK',
    '.KYYYYYyyyK.',
    '..KYYyyyyK..',
    '...KYYyyK...',
    '....KKKK....'
  ],
  [
    '.....KK.....',
    '....KYYK....',
    '...KYYYyK...',
    '..KYYYYyyK..',
    '..KYWYYYyK..',
    '..KYWYYYyK..',
    '.KYYWYYYyyK.',
    '.KYYWYYYyyK.',
    '.KYYWYYYyyK.',
    '.KYYWYYYyyK.',
    '..KYWYYYyK..',
    '..KYWYYyyK..',
    '..KYYYYyyK..',
    '...KYyyyK...',
    '....KYyK....',
    '.....KK.....'
  ],
  [
    '.....KK.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....Ky.....',
    '.....KK.....'
  ],
  [
    '.....KK.....',
    '....KYYK....',
    '...KYYYyK...',
    '..KYYYYyyK..',
    '..KYWYYYyK..',
    '..KYWYYYyK..',
    '.KYYWYYYyyK.',
    '.KYYWYYYyyK.',
    '.KYYWYYYyyK.',
    '.KYYWYYYyyK.',
    '..KYWYYYyK..',
    '..KYWYYyyK..',
    '..KYYYYyyK..',
    '...KYyyyK...',
    '....KYyK....',
    '.....KK.....'
  ]
]

// cannon shot, 18x12, flying left (mirrored for right)
export const BULLET = [
  '.....KK...........',
  '..KKKKKKKKKKKKKWK.',
  '.KKKKKKKKKKKKKKWK.',
  '.KKKWWKKKKKKKKKWK.',
  'KKKKWKKKKKKKKKKWK.',
  'KKKKKKKKKKKKKKKWK.',
  'KKKKKKKKKKKKKKKWK.',
  'KKKKKKKKKKKKKKKWK.',
  '.KKKKKKKKKKKKKKWK.',
  '.KKKKKKKKKKKKKKWK.',
  '..KKKKKKKKKKKKKWK.',
  '.....KK...........'
]

// the winged power-up a ? block sometimes gives, 22x15
export const WING = [
  '........KKK...........',
  '......KKWWWK..........',
  '....KKWWWWWK..........',
  '..KKWWWWWWWK..........',
  '.KWWWWWWWWWKKKK.......',
  'KWWWWWWWWWKYYYYKKK....',
  '.KKWWWWWWYYYYYYYYYK...',
  '...KKWWWYYYYYYYYYYYK..',
  '.....KYYYYYYYYYYYYyYK.',
  '.....KYYYYYYYYYYYYYyK.',
  '.....KYYYYYYYYYYYYyyK.',
  '.....KYYYYYYYYYYYyyyK.',
  '......KYyyYYYYYyyyyK..',
  '.......KYyyyyyyyyyK...',
  '........KKKYyyyKKK....'
]

// the ? on a block and on the flag, 10x14
export const QMARK = [
  '..KKKKKK..',
  '.KKKKKKKK.',
  'KKK....KKK',
  'KKK....KKK',
  '.......KKK',
  '......KKK.',
  '....KKKK..',
  '...KKK....',
  '...KKK....',
  '..........',
  '..........',
  '...KKK....',
  '...KKK....',
  '...KKK....'
]

// cannon, 26x24, muzzle left: B barrel, b highlight, R rings, W wooden carriage, w dark wood
export const CANNON = [
  '..........................',
  '..........................',
  '..........................',
  '.KKK......................',
  'KRRRK..........KKKKKKKK...',
  'KRRRKKKKKKKKKKKBBBBBBBBK..',
  'KRRRBBBBBBBBBBBBRRBBBBBBK.',
  '.KRRBbbbbbbbbbbBRRBbbBBBK.',
  '.KRRBBBBBBBBBBBBRRBBBBBBK.',
  '.KRRBBBBBBBBBBBBRRBBBBBBBK',
  '.KRRBBBBBBBBBBBBRRBBBBBBBB',
  '.KRRBBBBBBBBBBBBRRBBBBBBBK',
  '.KRRBBBBBBBBBBBBRRBBBBBBK.',
  '.KRRBBBBBBBBBBBBRRBBBBBBK.',
  'KRRRBBBBBBBBBBwwRRBBBBBBK.',
  'KRRRKKKKKKKKwwwwwwWWWWWK..',
  'KRRRK.....KwwWWwWwwWWWWK..',
  '.KKK......KwWWWwWWwWWWWK..',
  '.........KwwWWWwWWwwWWWK..',
  '.........KwwwwwbwwwwWWWK..',
  '........KWwwWWWwWWwwwwwK..',
  '.........KKwwWWwWwwKKKK...',
  '...........KwwwwwwK.......',
  '............KKwwKK........'
]

// small HUD and effect sprites
export const COIN_SMALL = ['..KKKK..', '.KYYYYK.', 'KYWYYYyK', 'KYWYYYyK', 'KYWYYYyK', 'KYWYYYyK', '.KyyyyK.', '..KKKK..']
export const HEART = ['.KK.KK.', 'KRRKRRK', 'KRRRRRK', '.KRRRK.', '..KRK..', '...K...']
export const SPARK = [
  ['.......', '.......', '...W...', '..WWW..', '...W...', '.......', '.......'],
  ['...W...', '...W...', '.......', 'WW.W.WW', '.......', '...W...', '...W...'],
  ['W.....W', '.......', '..W.W..', '.......', '..W.W..', '.......', 'W.....W']
]
