// Questions and approvals as cards.
import { Button, Codicon, jsx, jsxs, useEffect, useRef, useState } from '../sdk.js'
import { answerBuildPrompt, openInFullChat } from '../build-chat/actions.js'
import { APPROVAL_LABELS } from '../build-chat/requests.js'
import { AGENT } from '../core/ids.js'

export const SUGGESTED = /\s*\((recommended|suggested)\)\s*$/i

function BuildQuestions({ stored, item }) {
  const payload = item.payload ?? {}
  const questions = Array.isArray(payload.questions) && payload.questions.length
    ? payload.questions
    : [{ qid: 'q0', question: payload.question ?? '', choices: payload.choices ?? [] }]
  const [answers, setAnswers] = useState({})
  const [own, setOwn] = useState({})
  const [sending, setSending] = useState(false)
  const complete = questions.every(question => answers[question.qid])
  const pick = (qid, value) => setAnswers(current => ({ ...current, [qid]: value }))
  const box = useRef(null)

  // Number keys pick a choice for the first question still open (not while typing).
  useEffect(() => {
    const onKey = event => {
      const target = event.target

      if (event.metaKey || event.ctrlKey || event.altKey || (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName ?? '')) || target?.isContentEditable) {
        return
      }

      const number = Number(event.key)
      const open = questions.find(question => !answers[question.qid]) ?? questions[questions.length - 1]
      const choices = Array.isArray(open?.choices) ? open.choices : []

      if (number >= 1 && number <= choices.length) {
        event.preventDefault()
        pick(open.qid, choices[number - 1])
      }
    }

    window.addEventListener('keydown', onKey)

    return () => window.removeEventListener('keydown', onKey)
  }, [answers])

  const send = async () => {
    setSending(true)

    try {
      await answerBuildPrompt(stored, item, answers)
    } finally {
      setSending(false)
    }
  }

  return jsxs('div', {
    className: 'cs-b-qs',
    ref: box,
    children: [
      ...questions.map((question, number) =>
        jsxs(
          'div',
          {
            className: 'cs-b-q',
            children: [
              jsxs('p', {
                className: 'cs-b-qt',
                children: [questions.length > 1 ? jsx('span', { className: 'cs-faint', children: `${number + 1} of ${questions.length} · ` }) : null, question.question]
              }),
              jsx('div', {
                className: 'cs-b-choices',
                children: (Array.isArray(question.choices) ? question.choices : []).map((choice, index) => {
                  const suggested = SUGGESTED.test(choice)
                  const label = choice.replace(SUGGESTED, '')

                  return jsxs(
                    'button',
                    {
                      'aria-pressed': answers[question.qid] === choice,
                      className: 'cs-b-choice',
                      onClick: () => pick(question.qid, choice),
                      type: 'button',
                      children: [
                        jsx('kbd', { children: index + 1 }),
                        jsx('span', { className: 'cs-grow', children: label }),
                        suggested ? jsx('span', { className: 'cs-b-sugg', children: 'Suggested' }) : null
                      ]
                    },
                    choice
                  )
                })
              }),
              jsx('input', {
                'aria-label': 'Your own answer',
                className: 'cs-b-own',
                onChange: event => {
                  const value = event.target.value

                  setOwn(current => ({ ...current, [question.qid]: value }))
                  pick(question.qid, value.trim() ? value : undefined)
                },
                placeholder: 'Or type your own answer',
                value: own[question.qid] ?? ''
              })
            ]
          },
          question.qid
        )
      ),
      jsxs('div', {
        className: 'cs-row',
        children: [
          jsx(Button, { disabled: !complete || sending, onClick: () => void send(), size: 'sm', children: sending ? 'Sending…' : 'Send answer' }),
          jsx('span', { className: 'cs-faint cs-grow', children: `${AGENT} is waiting for you` }),
          jsx(Button, { onClick: () => openInFullChat(stored), size: 'sm', variant: 'ghost', children: 'Answer in full chat' })
        ]
      })
    ]
  })
}

export function BuildPromptCard({ stored, item }) {
  const payload = item.payload ?? {}
  const approval = item.kind === 'approval'
  const choices = (Array.isArray(payload.choices) && payload.choices.length ? payload.choices : ['once', 'deny']).filter(choice => APPROVAL_LABELS[choice])

  return jsxs('div', {
    className: `cs-b-card ${approval ? 'warn' : 'ask'}`,
    'data-prompt': 'open',
    children: [
      jsxs('div', {
        className: 'cs-row',
        children: [
          jsx(Codicon, { name: approval ? 'shield' : 'comment-discussion', size: 14 }),
          jsx('b', { children: approval ? `${AGENT} needs your OK` : `${AGENT} is asking` })
        ]
      }),
      approval ? jsx('p', { className: 'cs-small', children: payload.description || payload.tool_name || 'A protected action' }) : null,
      approval && payload.command ? jsx('pre', { className: 'cs-b-cmd', children: payload.command }) : null,
      approval
        ? jsxs('div', {
            className: 'cs-row',
            children: [
              ...choices.map(choice =>
                jsx(Button, { onClick: () => void answerBuildPrompt(stored, item, choice), size: 'sm', variant: choice === 'deny' ? 'outline' : 'default', children: APPROVAL_LABELS[choice] }, choice)
              ),
              jsx('span', { className: 'cs-grow' }),
              jsx(Button, { onClick: () => openInFullChat(stored), size: 'sm', variant: 'ghost', children: 'Answer in full chat' })
            ]
          })
        : jsx(BuildQuestions, { item, stored })
    ]
  })
}
