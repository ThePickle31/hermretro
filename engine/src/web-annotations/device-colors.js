// The player's device finishes, in their order, and the rail places that move some of them: ModRetro's Supply Co.
// and DevDay editions come first. A host serving the player may serve its own module at this name.
export const DEVICE_COLORS = [
    { id: "codex", name: "DevDay Edition", background: "#ffffff", ink: "#27272b" },
    { id: "transparent-green", name: "Transparent Green", background: "#bedc63", ink: "#27272b" },
    { id: "transparent-red", name: "Transparent Red", background: "#e65c62", ink: "#27272b" },
    { id: "transparent-smoke", name: "Transparent Smoke", background: "#85838a", ink: "#27272b" },
    { id: "transparent-purple", name: "Transparent Purple", background: "#a17bb5", ink: "#27272b" },
    { id: "supply-co", name: "Supply Co. Edition", background: "#bbb0c9", ink: "#27272b" },
    { id: "cloud", name: "Cloud", background: "#e5e6e3", ink: "#27272b" },
    { id: "midnight", name: "Midnight", background: "#4e4f55", ink: "#f5f5f3" },
    { id: "wave", name: "Wave", background: "#6dd6de", ink: "#27272b" },
    { id: "leaf", name: "Leaf", background: "#61c55a", ink: "#27272b" },
    { id: "inferno", name: "Inferno", background: "#ff6d1f", ink: "#27272b" },
    { id: "volt", name: "Volt", background: "#efbf22", ink: "#27272b" },
    { id: "bubblegum", name: "Bubblegum", background: "#ecafc6", ink: "#27272b" },
];
export const DEVICE_RAIL_ORDER = { "supply-co": -2, codex: -1 };
