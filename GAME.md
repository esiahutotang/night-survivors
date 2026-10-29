# Night Survivors — design (CDT501 Lecture 9)

A tiny game in the "survivors" style: you only walk, your weapons attack by themselves,
enemies come from every side, you grow stronger every level. Names, numbers and pictures are our own.

## Goal
- Survive until **2:00**: then the game shows VICTORY.
- Hero HP reaches 0: GAME OVER.
- Use Retry on the end screen to play again, or Home to choose a mode.

## Screen and controls
- Window 390 x 700 (portrait, like a phone). The camera follows the hero.
- The floor is one tile repeated forever: the map has no edges.
- Computer: the hero walks toward the mouse pointer and keeps walking as long as the pointer
  is more than 12 px away from him, even when the mouse does not move.
- Phone: the hero walks toward the finger while it touches the screen and stops when it is lifted.
- Click or tap a card to choose it. P pauses.

## Hero
| Speed | HP | Hit radius | Gem magnet radius |
|---|---|---|---|
| 120 px/s | 100 | 12 px | 60 px |

## Weapons (start with Spark Wand; at most 3 weapons; levels 1–5)
| Weapon | What it does | Level 1 | Each extra level |
|---|---|---|---|
| Spark Wand | shoots a spark (speed 400 px/s) at the nearest enemy | 10 damage, every 0.8 s, 1 spark | +3 damage, 0.08 s faster; +1 spark at levels 3 and 5 |
| Spin Blades | blades circle the hero at 60 px, one turn every 1.5 s; each blade hits an enemy at most every 0.5 s | 2 blades, 8 damage | +3 damage; +1 blade at levels 2 and 4 |
| Holy Ring | hurts every enemy inside a circle around the hero, every 0.5 s | 5 damage, radius 50 px | +2 damage, +10 px radius |

## Passive items (levels 1–5)
| Item | Each level |
|---|---|
| Swift Boots | +10% walking speed |
| Big Heart | +20 max HP and heal 20 |
| Magnet | +30 px gem magnet radius |

## Enemies
| Enemy | HP | Speed | Damage | XP | Picture |
|---|---|---|---|---|---|
| Bat | 8 | 100 | 5 | 1 | bat.png |
| Slime | 30 | 55 | 8 | 2 | slime.png |
| Ghost | 15 | 135 (faster than you) | 6 | 2 | ghost.png |
| Boss: Demon | 800 | 85 | 20 | 0 | demon.png, drawn twice as big |

An enemy that touches the hero hurts him at most once every 0.5 s.

## How enemies appear (the map is endless, so enemies come to you)
- Every 1 s: if fewer enemies are alive than the **minimum** for this time, spawn new ones
  (at most 8 per second) until the minimum is reached.
- New enemies appear at a random point on a circle 380 px from the hero, just outside the screen.
- Any normal enemy more than 700 px from the hero is removed. New ones will come.
- The boss is never removed: if it is more than 600 px away, move it back to the 380 px circle.
- Never more than 120 enemies alive.

| From | Enemy types | Minimum alive |
|---|---|---|
| 0:00 | Bat | 12 |
| 0:15 | Bat | 20 |
| 0:30 | Bat, Slime | 28 |
| 0:45 | Slime, Ghost | 36 |
| 1:00 | Bat, Ghost | 45 |
| 1:15 | Bat, Slime, Ghost | 55 |
| 1:30 | the boss appears once; Bat, Slime | 55 |
| 1:45 | Bat | 75 |

## XP and level-up
- Every dead enemy drops a gem worth its XP. Gems inside the magnet radius fly to the hero (300 px/s).
- XP needed for the next level: 5 at level 1, then 3 more each level (5, 8, 11, 14, ...).
- Level-up: the game pauses and shows 3 random cards. A card is a new weapon (if fewer than 3),
  +1 level for a weapon you have, or a passive item. Never offer something already at level 5.
  If nothing is left, offer "Heal 30 HP".

## What the screen shows
- Top left: HP bar (red), XP bar (blue) and "Lv 3".
- Top right: the timer, for example "0:45 / 2:00".
- Bottom: what you have, for example "Spark 2  Blades 1  Boots 1".
- Level-up: 3 big cards, each with a name, the new level and one line of text.
- End: VICTORY or GAME OVER, with time, kills and level.

## Build steps (build one step at a time, only when asked)
1. **Core:** hero and controls, camera and repeating floor, Bats with the spawning rules,
   contact damage, Spark Wand, HP, GAME OVER and play again. Coloured shapes, no pictures yet.
2. **Pictures:** make_assets.py makes 3x bigger copies of raw_art/ with Pillow (no blurring),
   plus two bright crystal gems coloured from raw_art/gem.png: blue for XP 1, pink for XP 2.
   main.py draws them.
3. **Growth:** gems, XP, level-up cards, all weapons and passive items.
4. **Waves:** the whole table above, Slime, Ghost, the boss, VICTORY at 2:00, the timer.
5. **Sound and feel:** make_sounds.py (standard library only) makes short sounds for hits,
   gems, level-up, getting hurt and the end; damage numbers, a flash when an enemy dies,
   a small shake when the hero is hurt.

## Daily Challenge and personal records

Choose Normal or Daily Challenge on the home screen. Normal follows the tables
above. Daily applies one preset from data/challenges.json to a copy of these
rules, with date-based seeds and separate spawn/upgrade random streams.
Challenge dates reset at UTC+8 midnight. A running game keeps its original date
and preset; retry uses the current date. The survive-to-win goal stays 2:00.

Best completed runs compare (victory, survival time in milliseconds, kills,
level), descending. Normal, each daily date, and each preset's historical best
are separate, and gameplay/rules versions are isolated. The end screen saves
once, highlights a new best, and offers Retry and Home. The home screen lists
personal bests. Saves are local to this browser/site or desktop folder, with
an explicit session-only message when persistent storage is unavailable.
