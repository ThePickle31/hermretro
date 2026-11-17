// The Emulator page: the bar above the player and the captures strip.
import { Button, Codicon, jsx, jsxs, Tip, useQuery } from '#sdk'
import { callStudio, studioError } from '#app/backend.js'
import { DEMO_ID, ID } from '#app/ids.js'
import { RPC_CAPTURES } from '#app/rpc.js'
import { Slot } from '#app/slots.js'
import { AsyncButton } from '#shared/ui/page.js'
import { Small } from '#shared/ui/text.js'

function Captures({ game, open }) {
  const captures = useQuery({
    queryKey: [ID, 'captures', game?.id ?? null],
    queryFn: () => callStudio(RPC_CAPTURES, { id: game.id }),
    enabled: Boolean(open && game),
    refetchInterval: open ? 5_000 : false,
    retry: false
  })

  if (!open) {
    return null
  }

  const list = captures.data?.captures ?? []

  return jsx('div', {
    className: 'cs-rp-caps',
    children: captures.isError
      ? jsx(Small, { children: studioError(captures.error, 'list captures') })
      : list.length
        ? list.map(capture =>
            jsxs(
              'figure',
              {
                children: [
                  capture.kind === 'screenshot' || /\.png$/i.test(capture.path ?? '')
                    ? jsx('img', { alt: '', src: capture.url })
                    : jsx('video', { controls: true, src: capture.url }),
                  jsx('figcaption', { title: capture.path, children: String(capture.path ?? '').split('/').pop() })
                ]
              },
              capture.path ?? capture.url
            )
          )
        : jsx(Small, {
            children: "Screenshots and videos you take with the camera and video buttons beside the device land here and in the game's captures folder."
          })
  })
}

/** The rebuilt banner and the bar above the player: only the player's controls. Below a narrow width
 *  the bar's buttons drop their labels (`.cs-lbl`) and keep their icons and tooltips. */
export function EmulatorBar({ ctx, game, player, focused, hardwareOn, rebuilt, capturesOpen, onAsk, onToggleCaptures, onFull, onReload, onLater }) {
  const onDemo = game?.id === DEMO_ID

  return [
    rebuilt
      ? jsxs(
          'div',
          {
            className: 'cs-reload',
            role: 'status',
            children: [
              jsx('span', { className: 'dot' }),
              jsxs('span', { children: [jsx('b', { children: `Hermes rebuilt ${game.title}` }), jsx('span', { className: 'cs-small', children: ' · the player is still running the earlier build' })] }),
              jsx('span', { className: 'cs-grow' }),
              jsxs(Button, { onClick: onReload, size: 'sm', variant: 'default', children: [jsx(Codicon, { name: 'refresh', size: 14 }), 'Load the new build'] }),
              jsx(Button, { onClick: onLater, size: 'sm', variant: 'ghost', children: 'Later' })
            ]
          },
          'reload'
        )
      : null,
    jsxs(
      'div',
      {
        className: 'cs-rp-bar',
        children: [
          jsx('span', { className: 'cs-grow' }),
          jsx(Tip, {
            label: 'Lit while the player has keyboard focus. Keys typed on this page also reach the game.',
            children: jsxs('span', { className: focused ? 'cs-rp-focus on' : 'cs-rp-focus', children: [jsx('i', {}), jsx('span', { className: 'cs-lbl', children: 'Keyboard' })] })
          }),
          game && !onDemo ? jsx(Slot, { name: 'emulator.barActions', props: { ctx, game, hardwareOn } }) : null,
          jsx(AsyncButton, { disabled: !player?.data?.url, icon: 'comment-discussion', run: onAsk, title: "Puts this frame and a note into the game's chat, not sent", variant: 'ghost', children: 'Ask Hermes' }),
          jsx(Tip, {
            label: 'Screenshots and videos of this game',
            children: jsx('span', {
              style: { display: 'inline-flex' },
              children: jsxs(Button, {
                'aria-label': 'Captures',
                disabled: !game,
                onClick: onToggleCaptures,
                size: 'sm',
                variant: capturesOpen ? 'secondary' : 'ghost',
                children: [jsx(Codicon, { name: 'device-camera', size: 14 }), jsx('span', { className: 'cs-lbl', children: 'Captures' })]
              })
            })
          }),
          jsx(Tip, {
            label: 'Full screen',
            children: jsx('span', {
              style: { display: 'inline-flex' },
              children: jsx(Button, { 'aria-label': 'Full screen', disabled: !player?.data?.url, onClick: onFull, size: 'sm', variant: 'ghost', children: jsx(Codicon, { name: 'screen-full', size: 14 }) })
            })
          })
        ]
      },
      'bar'
    ),
    jsx(Captures, { game, open: capturesOpen }, 'caps')
  ]
}
