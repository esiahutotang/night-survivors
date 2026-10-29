# Night Survivors — Step 5: Sound and feel

界面已汉化：升级卡片、武器与道具、状态栏、暂停和结束画面均为简体中文。
中文使用随游戏打包的站酷快乐体（SIL OFL 1.1），手机无需安装字体。
字体来源：https://github.com/google/fonts/tree/main/ofl/zcoolkuaile
授权文件：assets/OFL-ZCOOLKuaiLe.txt。汉化不改变游戏数值。

Play online: https://esiahutotang.github.io/night-survivors/
On a phone, wait for the first download, then tap the page to start and enable
sound. Hold and drag a finger to walk; lift it to stop. Tap upgrade cards and
the end screen as usual. The page keeps the game's portrait proportions.

Install `pygame-ce` with `py -3.13 -m pip install pygame-ce`, then run
`py -3.13 main.py` from this folder.

Move the mouse away from the hero to walk; the hero keeps walking toward the
pointer even if the mouse stays still. On a touchscreen, hold and drag to walk;
lift your finger to stop. The Spark Wand automatically fires at nearby enemies.
Collect blue (XP 1) and pink (XP 2) gems to gain XP. Nearby gems fly toward you.
At each level, play freezes: click or tap one of three cards to choose an upgrade.
Add Spin Blades or Holy Ring, improve your weapons, or gain speed, HP or magnet
range. Weapons and passive items each reach level 5. The HP and XP bars are at
the top, and your equipment levels are at the bottom.
Survive until 2:00 to win. The timer pauses while choosing upgrades or pressing
P to pause. At VICTORY or GAME OVER, click or tap to start again.

Waves follow the complete table in GAME.md, bringing Bats, Slimes and faster
Ghosts. The Demon appears once at 1:30, drawn twice as big. You only need to
survive to win, even if the boss is alive. Normal enemies too far away disappear;
the boss instead returns near you. At most 8 enemies spawn per second and no
more than 120 are alive.
All gameplay numbers are in data/game.json, including the adjusted Spark Wand
base damage of 20.

Run rule checks with `py -3.13 -m unittest`. The rules use a fixed 1/60-second
step and have no drawing-library dependency.

The finished PNGs are included in assets/. To rebuild them, install Pillow with
`py -3.13 -m pip install pillow`, then run `py -3.13 make_assets.py`.
This makes exact 3x copies with sharp pixel edges and preserves transparency.
It also makes blue (XP 1) and pink (XP 2) crystal gems. Bats drop XP 1,
Slimes and Ghosts drop XP 2, and the Demon drops no XP.
The game loads finished files only; it never runs Pillow or the builder.
Original files in raw_art/ are preserved, and the Kenney CC0 license is copied
alongside the finished assets.

Short sounds play for hits, gem pickups, level-ups, getting hurt, victory and
game over. Damage numbers rise and fade, defeated enemies briefly flash white,
and getting hurt causes a small camera shake. The HUD stays still, and the shake
does not affect where you walk or the game rules. Restarting clears the effects
and stops old sounds. The game still runs silently if audio is unavailable.

Finished WAV files are included in sounds/. Rebuild them with
`py -3.13 make_sounds.py`; this separate script uses only Python's standard
library. The game prefers an .ogg file when present, otherwise it uses .wav.
Sound settings and effect timings are in data/game.json. No sound generation
or image generation is imported by the game.

## Rebuild the browser version

Install the web builder with `py -3.13 -m pip install -r requirements-web.txt`.
In PowerShell, run these commands from this folder:

```powershell
$env:PYTHONUTF8 = '1'
py -3.13 -m pygbag --build --disable-sound-format-error .
New-Item -ItemType Directory -Force docs
Copy-Item build/web/* docs/ -Recurse -Force
New-Item -ItemType File -Force docs/.nojekyll
```

The additional sound flag allows the included standard PCM WAV files; the
runtime loads these finished sounds without importing the sound builder.
`pygbag.ini` excludes offline scripts, tests, original art and docs from the
game package. `default.tmpl` provides the portrait layout and tap-to-start
message. Commit the updated docs files and push main to update GitHub Pages.
Pages must use the main branch and /docs folder. The first visit downloads the
Python runtime from pygbag's CDN, so it takes longer than later visits.

## Upgrade cards

Upgrade cards and the equipment bar share seven original pixel icons, drawn once
at startup with pygame (no new asset or runtime dependencies). Cards distinguish
new weapons, weapon upgrades, passive upgrades and healing. Each card shows the
current and next level, plus actual before/after stats from data/game.json.
New weapons show their starting stats; healing previews respect missing HP.
Weapon previews use the same stat calculation as combat and do not change the
game, its random state, or its balance. The full card remains a mouse/touch target.
