// The two skies: day (light theme) and night (dark theme). Each palette gives the tiles' colours and the inks each
// sprite's letters map to (art.js, art-enemies.js); the Nous Girl stays black and white in both, with a white
// outline on the night sky so she never disappears into it.

const GOLD = { K: '#5a3214', Y: '#f7c548', W: '#fff6c0', y: '#c08a1e' }

export const PAL = {
  day: {
    sky: ['#7cc8ff', '#a6dbff', '#d2efff'], stars: false, cloud: ['#ffffff', '#cbe6f7'],
    hill: ['#a8dcc4', '#7cc79a'], grass: ['#a6ec6e', '#5cb24a', '#2f7a3a'], dirt: ['#c98a4b', '#9a5f2e', '#6b3d1d'],
    brick: ['#d0703c', '#7a3318', '#f2a272'], block: ['#f7c548', '#c08a1e', '#fff2a8', '#5a3214'], used: ['#a0693a', '#5a3214'],
    ledge: ['#f0e0b8', '#c09a62', '#6b4f2a'], pipe: ['#5ec46a', '#2f7f3c', '#bdf2a4', '#123a1a'], water: ['#3a8fd8', '#8fd0f8'],
    deco: ['#3c9a4e', '#1f6b33', '#ff8fb0', '#fff36a'], hud: ['#10131c', '#f4f4f0', '#ff5a6e', '#f7c548', '#3a3f4e'],
    girl: { K: '#000000', W: '#ffffff' }, girlLine: null,
    bug: { K: '#16131f', E: '#d84a4a', e: '#ff9a8a', d: '#7a2430', W: '#ffffff' },
    spiny: { K: '#1a1a24', S: '#6a4fb5', s: '#a890e8', P: '#ffffff', F: '#ffd8a8' },
    blob: { K: '#1a1a24', G: '#5ccf7a', g: '#2f8a4e', W: '#ffffff' },
    bat: { K: '#16131f', B: '#7a4fb5', W: '#ffe27a' },
    cannon: { K: '#1a1a24', B: '#3a3f4e', b: '#9aa2b4', R: '#626a7e', W: '#c98a4b', w: '#6b3d1d' },
    coin: GOLD, bullet: { K: '#1a1a24', W: '#ffffff' }, wing: { W: '#ffffff', K: '#16131f', Y: '#f7c548', y: '#c08a1e' },
    spark: '#ffffff', moon: null
  },
  night: {
    sky: ['#070b22', '#0e1640', '#18245c', '#243474'], stars: true, cloud: ['#2c3c7a', '#1f2c62'],
    hill: ['#18244e', '#121c40'], grass: ['#4ad0a0', '#23907a', '#124a46'], dirt: ['#34305e', '#252248', '#17142e'],
    brick: ['#5a4a92', '#221c44', '#8e7ec8'], block: ['#4a84fe', '#2448b0', '#b0ccff', '#070b22'], used: ['#34305e', '#17142e'],
    ledge: ['#a8b8f0', '#5a6aa8', '#202a5a'], pipe: ['#3fb0c4', '#1f6a82', '#a6f0fa', '#08283a'], water: ['#1c3ea8', '#4a84fe'],
    deco: ['#23907a', '#124a46', '#ff6ad5', '#fff36a'], hud: ['#04060e', '#e6edf3', '#ff5a6e', '#f7c548', '#283050'],
    girl: { K: '#000000', W: '#ffffff' }, girlLine: '#ffffff',
    bug: { K: '#05060c', E: '#e05a7a', e: '#ffa0b8', d: '#702040', W: '#ffffff' },
    spiny: { K: '#05060c', S: '#e08a3a', s: '#ffc070', P: '#f4f1ea', F: '#ffe0b8' },
    blob: { K: '#05060c', G: '#5ad8e0', g: '#2a8aa0', W: '#ffffff' },
    bat: { K: '#05060c', B: '#8a6ad8', W: '#ffe27a' },
    cannon: { K: '#05060c', B: '#3a4262', b: '#9aa6cc', R: '#66729a', W: '#8a5a34', w: '#4a2c18' },
    coin: GOLD, bullet: { K: '#05060c', W: '#e6edf3' }, wing: { W: '#ffffff', K: '#05060c', Y: '#f7c548', y: '#c08a1e' },
    spark: '#ffffff', moon: '#f4f0d8'
  }
}
