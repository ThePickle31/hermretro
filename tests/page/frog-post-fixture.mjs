// Fresh library and gateway fixtures for the Build and Games scenarios.
export const frogPost = (overrides = {}) => ({
  id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio', state: 'ready',
  rom: null, webExport: true, thumb: null, chat: null, error: null, ...overrides
})

export const lamplight = () => ({
  id: 'aaa000aaa000', title: 'Lamplight', projectRoot: '/home/u/games/Lamplight', kind: 'gbstudio', state: 'unbuilt',
  rom: null, webExport: false, thumb: null, chat: null, session: { storedId: 'st-new-1' }, error: null
})

export const toolCall = (id, name, args = {}) => ({ id, function: { name, arguments: JSON.stringify(args) } })

export const robinBuildReport = () => ({
  title: 'Robin in the sky', summary: 'A little red robin in a big daytime sky. Fly anywhere with the D-pad.',
  changes: [{ kind: 'added', text: 'Robin sprite, 3 views', asset: 'assets/sprites/bird.png' }, { kind: 'changed', text: 'Camera follows the player' }],
  tested: ['Robin faces where it flies', 'Camera follows'], untested: ['Sound'],
  notes: ['It only flaps while moving'], suggestions: ['Flap while idle', 'Fly faster']
})

export const reportedRobinBuild = (reply, report = robinBuildReport()) => [
  { role: 'user', content: 'make a bird game', timestamp: 2000 },
  { role: 'assistant', content: '', timestamp: 2001, tool_calls: [
    toolCall('b1', 'chromatic_rom_build'), toolCall('r1', 'chromatic_build_report', report)
  ] },
  { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 2010 },
  { role: 'tool', tool_call_id: 'r1', content: JSON.stringify({ ok: true, report }), timestamp: 2011 },
  { role: 'assistant', content: reply, timestamp: 2012 }
]
