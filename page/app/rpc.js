// Every backend RPC the page calls (`plugin.hermretro.<name>`): RPC_<NAME>, and RPC_NAMES (name -> method).
// The names are generated from the backend's @rpc declarations into ./rpc-names.js (never edit that file;
// node tools/bundle/bundle.mjs regenerates it). Their shapes are in .agents/skills/hermretro-dev-architecture/references/contract.md.
export * from './rpc-names.js'
