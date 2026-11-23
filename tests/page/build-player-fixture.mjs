import assert from 'node:assert/strict'

export const playerUrl = gameId => `http://127.0.0.1:4567/tok/${gameId}/index.html`
export const playable = game => ({ ...game, state: 'ready', webExport: true, web: { sha256: `web-${game.id}`, builtAt: Date.now() / 1000 } })

export function presentation(game, runtime, presentedAt) {
  return {
    type: 'tool.complete',
    session_id: runtime,
    payload: {
      tool_id: `present-${game.id}`,
      name: 'chromatic_present_game',
      args: {},
      result: { ok: true, studio: { gameId: game.id, title: game.title, note: `Try ${game.title}.`, presentedAt, buildConversation: true } }
    }
  }
}

export function buildView(node, act, scenario) {
  const frame = () => node.querySelector('.cs-ip iframe')
  const frameUrl = () => frame()?.getAttribute('src')?.split('?')[0] ?? null
  const assertClosed = () => {
    assert.equal(frameUrl(), null, 'no game frame should be open')
    assert.equal(Boolean(node.querySelector('.cs-ip')), false, 'the inline player should be closed')
  }
  return {
    assertSelected: (id, title) => {
      assert.equal(scenario.storage.buildSelected, id)
      assert.equal(node.querySelector('.cs-b-sw h2')?.textContent, title)
    },
    assertBusy: expected => assert.equal(Boolean(node.querySelector('button[aria-label="Stop"]')), expected),
    assertClosed,
    assertPlaying: game => {
      assert.equal(frameUrl(), playerUrl(game.id))
      assert.equal(frame().getAttribute('title'), `${game.title} in ModRetro's Chromatic player`)
      assert.equal(node.querySelectorAll('.cs-ip iframe').length, 1)
    },
    play: () => act(async () => { node.querySelector('.cs-b-pc-go').click() }),
    closePlayer: () => act(async () => { node.querySelector('button[aria-label="Close the game"]').click() }),
    selectGame: async game => {
      await act(async () => { node.querySelector('.cs-b-sw').click() })
      const item = [...node.querySelectorAll('.cs-b-sw-list button')].find(button => button.querySelector('b')?.textContent === game.title)
      assert.ok(item, `the switcher lists ${game.title}`)
      await act(async () => { item.click() })
    }
  }
}
