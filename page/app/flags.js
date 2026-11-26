// Feature flags: unfinished work on main, hidden from users until its flag is shipped. This is the only list of
// them; .agents/skills/hermretro-dev-page/references/adding.md, "Behind a flag", walks through each step.
//
//   add      one line below: `<snake_name>: { hides: '<what it hides>', setting: false },`
//   hide     `flag: '<snake_name>'` in a page's or a tab's descriptor (app/registry.js checks the name)
//   turn on  HERMRETRO_FLAGS=<name>[,<name>] in the gateway's environment (backend/system/flags.py)
//   switch   `setting: true`, and a `flag_<snake_name>` bool (default false) in plugin.yaml's config_schema: a
//            switch in Hermes's plugin settings (tests/repo/test_lockstep.py keeps the two in step)
//   ship     delete its line here, its `flag:` lines and its plugin.yaml entry
export const FLAGS = Object.freeze({
})

/** The flags the status answer says are on: none until it answers. */
export const flagsOn = data => new Set(Array.isArray(data?.flags) ? data.flags : [])
