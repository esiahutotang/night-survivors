# Project rules (CDT501 Lecture 9)

## The project
A small game in Python with pygame-ce. GAME.md is the design: read it first and follow its numbers.

## Files
- rules.py: the game rules with a fixed time step (1/60 s). No pygame in this file.
- data/game.json: all the numbers from GAME.md. Changing a number there must not need a code change.
- main.py: window, drawing, sound and input. The main loop is `async def main()` with
  `await asyncio.sleep(0)` once per frame, and the file ends with `asyncio.run(main())`,
  so pygbag can run it in a web browser.
- main.py must NOT import PIL, wave, make_assets or make_sounds (they do not work in a browser).
  It only loads finished files from assets/ and sounds/ (a sound can be .ogg or .wav: use whichever exists).
- make_assets.py (Pillow) and make_sounds.py (standard library) are separate scripts I run on my computer.
- tests/: a few `unittest` tests for the rules in rules.py only (spawning, damage, XP and level-up,
  win and lose). No tests for drawing, pictures or sounds. Tests read the numbers from data/game.json.
- raw_art/: original pictures (Kenney, CC0). Never change, move or delete them.

## Rules for the agent
- Build only the step I ask for. Keep everything that already works.
- Use only Python's standard library, pygame-ce and Pillow. Ask before installing anything else.
- If Python is not installed (`python --version` fails or opens the Microsoft Store): on Windows run
  `winget install -e --id Python.Python.3.13`, then use `py -3.13` instead of `python` until I open a new
  terminal. On a Mac, ask me to install Python from https://www.python.org (it needs my password).
- If pygame-ce or Pillow is missing, install them with `python -m pip install pygame-ce pillow`
  (on a Mac: `python3 -m pip install pygame-ce pillow`). Install pygame-ce, not pygame.
- Only use pygame-ce functions and constants you are sure exist. If you are not sure, check with
  `python -c "import pygame; print(hasattr(pygame, 'NAME'))"`.
- Before you say it works: run `python -m unittest`, then run main.py for a few seconds without a window
  (SDL_VIDEODRIVER=dummy) while posting a few fake mouse moves, clicks and finger touches with
  `pygame.event.post`, so the input code runs at least once. Show me the real output.
- Explain what you did in simple English: I am learning to program.
- Do not run git commit unless I ask you to.
