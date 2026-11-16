export const FLYER_CSS = `
/* The flying Chromatic: the body and one wing drawn twice (the left one mirrored), each a 1-bit
   mask painted in the accent colour. Wings beat around the point where they meet the case; the
   whole thing lifts on each downstroke and drifts slowly, tilted like the old winged art. */
.cs-flyer { aspect-ratio: 100 / 108; container-type: inline-size; justify-self: center; margin-top: -6px; max-width: 460px; pointer-events: none; position: relative; width: 100%; }
.cs-flyer .drift, .cs-flyer .lift, .cs-flyer .tilt { inset: 0; position: absolute; }
.cs-flyer .drift { animation: cs-fly-drift 5.4s ease-in-out infinite; }
.cs-flyer .lift { animation: cs-fly-lift .9s ease-in-out infinite; }
.cs-flyer .tilt { transform: perspective(160cqi) translateX(-4cqi) scale(.82) rotateY(-14deg) rotateX(6deg) rotateZ(16deg); transform-style: preserve-3d; }
.cs-flyer .ink { background: var(--ui-accent); inset: 0; position: absolute; -webkit-mask: var(--m) center / 100% 100% no-repeat; mask: var(--m) center / 100% 100% no-repeat; }
.cs-flyer .body { height: 55.9cqi; left: 35cqi; position: absolute; top: 30cqi; width: 30cqi; z-index: 2; }
.cs-flyer .body .ink { --m: var(--cs-fly-body); }
.cs-flyer .wing { height: 41.4cqi; position: absolute; top: 11.6cqi; width: 42cqi; z-index: 1; }
.cs-flyer .wing .ink { --m: var(--cs-fly-wing); }
.cs-flyer .wing.r { animation: cs-flap-r .9s cubic-bezier(.45, 0, .3, 1) infinite; left: 60.7cqi; transform-origin: 3% 87.8%; }
.cs-flyer .wing.l { animation: cs-flap-l .9s cubic-bezier(.45, 0, .3, 1) infinite; left: -2.7cqi; transform-origin: 97% 87.8%; }
.cs-flyer .wing.l .ink { transform: scaleX(-1); }
.cs-flyer .shadow { animation: cs-fly-shadow 5.4s ease-in-out infinite; background: radial-gradient(closest-side, color-mix(in srgb, var(--ui-accent) 38%, transparent), transparent); height: 6cqi; left: 24cqi; position: absolute; top: 98cqi; width: 46cqi; }
@keyframes cs-flap-r { 0%, 100% { transform: rotate(-28deg); } 42% { transform: rotate(20deg) scaleY(.8); } }
@keyframes cs-flap-l { 0%, 100% { transform: rotate(28deg); } 42% { transform: rotate(-20deg) scaleY(.8); } }
@keyframes cs-fly-lift { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-2.4cqi); } }
@keyframes cs-fly-drift { 0%, 100% { transform: translateY(0) rotate(-1.5deg); } 50% { transform: translateY(-7cqi) rotate(1.5deg); } }
@keyframes cs-fly-shadow { 0%, 100% { opacity: .9; transform: scaleX(1); } 50% { opacity: .45; transform: scaleX(.7); } }
`
