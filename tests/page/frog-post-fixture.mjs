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

export const frogSprite = path => ({
  ok: true, path, name: path.split('/').pop(), relative: 'assets/sprites/frog.png',
  kind: 'sprite', width: 32, height: 16, bytes: 90, dataUrl: 'data:image/png;base64,iVBORw0KGgo=',
  sprite: { name: 'Frog', frameWidth: 16, frameHeight: 16, animSpeed: 15 }
})

export function frogJumpMessages() {
  const image = { assetPath: 'assets/sprites/frog.png' }
  const importCall = { name: 'chromatic_asset_import', arguments: image }
  const romCall = { name: 'chromatic_rom_build', arguments: {} }
  return [
    { role: 'user', content: 'make the frog jump', timestamp: 1000 },
    { role: 'assistant', content: [{ type: 'text', text: 'On it.' }], timestamp: 1001, tool_calls: [
      toolCall('v1', 'vision_analyze', { image_url: '/home/u/games/FrogPost/docs/art/frog.png', question: 'ok?' }),
      toolCall('w1', 'tool_call', { calls: [
        { ...importCall, arguments: { ...image, kind: 'sprite' } }, romCall
      ] })
    ] },
    { role: 'tool', tool_call_id: 'v1', name: 'vision_analyze', timestamp: 1004 },
    { role: 'tool', tool_call_id: 'w1', name: 'tool_call', args: { calls: [importCall] }, timestamp: 1020 },
    { role: 'tool', tool_call_id: 'w1', name: 'tool_call', args: { calls: [romCall] },
      content: JSON.stringify({ structuredContent: { success: true } }), timestamp: 1050 },
    { role: 'assistant', content: 'Added a jump.', timestamp: 1167 },
    { role: 'user', text: 'secret', display_kind: 'hidden' }
  ]
}
