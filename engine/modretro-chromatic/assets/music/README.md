# Bundled music

Four original songs that `music_compose {"bundled": "<name>"}` writes into a game as hUGETracker `.uge` files:

| Track | Use | Tempo |
|---|---|---|
| `bright-start` | title screen | 150 BPM |
| `meadow-walk` | overworld | 112 BPM |
| `cave-echo` | dungeon | 90 BPM |
| `victory-lap` | win or ending | 150 BPM |

Each `.json` is the song as `music_compose` input: sections of note lists, their order, the tempo
(`ticksPerRow`) and the instruments. They were written for hermretro by its maintainers, quote no
existing music, and are under hermretro's MIT license, so a game may ship them.
