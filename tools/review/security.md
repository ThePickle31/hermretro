Review a change to hermretro for security, read-only: branch {{branch}} at {{head}}, checked out for you
in {{checkout}}. Read it there, not in the change's own worktree, which moves on while you read. Nothing is
installed or built there, so build and run nothing: show each finding from the code. This pass reviews
{{scope}}: `{{diff}}`. Change nothing and write nothing to GitHub; the one file you write is {{findings}}.

What the change is for:

{{purpose}}

What was approved is in {{decisions}}: a finding that would change it goes under Out of scope. hermretro is a
Hermes plugin that runs on the user's own computer: a gateway process, a broker it starts, engine workers,
and loopback servers for the player. Look only for security defects the change introduces, holding it to the
rules in {{rules}} that cover its paths, above all those on the broker, the prepared engine copy, setup and
removal, the hardware approvals and the player's server. Read:

{{reading}}

Also look for:

- paths that escape their folder, links followed out of one, and files made with modes wider than they need;
- shell commands or arguments built from untrusted text (a game's files, a project's names, a request);
- a loopback route that serves data or acts on a game without its token and host check, or serves more than its
  route names; a tokenized URL reaching anywhere but where its route is meant to be opened (the page's player
  frame and captures, and `chromatic_present_game`'s `studio.playerUrl` in the chat);
- the hardware tools (`flash`, `play`, `setup`, capture) reached without the user's `hardware_enabled`
  setting and Hermes's approval prompt;
- downloaded or unpacked code trusted without its pinned SHA-256;
- tokens, credentials or a person's files reaching logs, errors, another profile, or the page beyond the URLs
  above.
{{earlier}}
Write the findings, most important first, each a heading with the evidence beneath it:

```
## Important: <path>:<line> <what is wrong>
How it is exploited or leaks, and what to change.
## Nit: <path>:<line> <a hardening worth making>
## Pre-existing: <path>:<line> <what is wrong>
## Question: <path>:<line> <a choice to justify>
## Out of scope: <path>:<line> <what>
```

Check each against the code, and leave out what you can't show. With nothing to report, write
`No findings.` alone.
