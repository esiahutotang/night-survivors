# Contributing to Night Survivors

Thanks for helping improve the game! We are a tiny team, so most of this guide
is about one thing: **keeping `main` always playable while several people work
in parallel without stepping on each other.**

The rules below are short on purpose. If anything is unclear, open an issue
and ask — that is always the right move.

## The short version

1. Never push directly to `main`. Everything goes through a pull request.
2. One feature = one branch = one PR. Keep branches short-lived (a few days).
3. All gameplay numbers live in `data/game.json` and `data/challenges.json` —
   never hardcode a number into code.
4. Never edit files in `assets/` or `sounds/` by hand. Change the source and
   regenerate (see below).
5. `python -m unittest` and `python tools/smoke_check.py` must pass before
   you open a PR. CI runs them again on every PR.

## Project layout

| Path | What it is | You may freely edit? |
|---|---|---|
| `rules.py` | Pure game rules, fixed 1/60 s step, **no pygame import** | Yes, via PR |
| `main.py` | Window, drawing, input, sound. Must stay browser-safe (no PIL, no `make_*` imports) | Yes, via PR |
| `data/game.json`, `data/challenges.json` | All gameplay numbers and daily-challenge presets | Yes, via PR — see *Balance changes* |
| `tests/` | Unittest suite for the rules layer; reads numbers from `data/` | Yes, via PR |
| `tools/smoke_check.py` | Headless run of the real game loop (SDL dummy drivers) | Yes, via PR |
| `raw_art/` | Original CC0 art sources | **Never change, move or delete** |
| `assets/`, `sounds/` | Generated finished files (committed so the game just works) | **Never hand-edit** — regenerate |
| `make_assets.py`, `make_sounds.py` | Generators that rebuild `assets/` / `sounds/` | Yes, via PR |
| `docs/` | The live GitHub Pages build (the online game itself) | Only in a release PR |

`AGENTS.md` documents the same rules for AI coding assistants. If you change
a rule here, update `AGENTS.md` too, and vice versa.

## Workflow: fork → branch → PR

Everyone contributes through a fork, so the upstream `main` branch only ever
changes via reviewed pull requests.

### 1. One-time setup

```bash
# Clone your fork (replace <you> with your GitHub username)
git clone https://github.com/<you>/night-survivors.git
cd night-survivors

# Add the upstream repo
git remote add upstream https://github.com/esiahutotang/night-survivors.git
git remote -v   # confirm: origin = your fork, upstream = the project repo
```

### 2. Keep your fork's main up to date

Do this before starting any new branch:

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

### 3. Create a short-lived feature branch

Branch names: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.

```bash
git checkout -b feat/my-new-feature main
```

Keep the branch alive for days, not weeks. The longer a branch lives apart
from `main`, the more likely conflicts get painful. If a feature is big,
split it into smaller PRs that each work on their own.

### 4. Make commits

- Commit message: short imperative subject in English, e.g.
  `Add daily challenges and device-local personal bests` (matches the
  existing history).
- One logical change per commit; avoid mixing balance tweaks with new
  features in the same PR when possible.
- Update `README.md` / `GAME.md` in the same PR if the change affects
  gameplay numbers, controls or the build.

### 5. Before opening the PR — run the checks locally

```bash
python -m unittest                 # rules layer tests
python tools/smoke_check.py        # headless real-loop check (--no-audio also works)
```

Both must pass. If your change touches `assets/` or `sounds/`, also rebuild
and commit the regenerated files (see next section).

### 6. Open the pull request

- Target `main` on the upstream repo, from your fork's branch.
- Fill in the PR description: what changed, why, and any gameplay impact.
  Screenshots are welcome when the UI changes — reviewers rely on this.
- CI (`.github/workflows/ci.yml`) runs the same checks on GitHub. The repo
  owner approves the first workflow run per new branch; after that it runs
  automatically. CI must be green before merge.
- If your branch falls behind `main` and conflicts appear, merge `main` into
  your branch (`git fetch upstream && git merge upstream/main`), resolve,
  re-run the local checks, and push again.
- After merge, delete the branch (GitHub's *Delete branch* button) and
  re-sync your fork's `main` (step 2).

## Balance changes have extra rules

Numbers in `data/game.json` and `data/challenges.json` are not cosmetic:

- Daily-challenge seeds and personal-best records are keyed to a
  **rules version**. Changing a gameplay number invalidates comparisons with
  old bests, so it needs a new rules version (see `records.py`).
- Balance changes therefore **always go through a PR** — never merge a
  balance tweak casually, even a one-number change.
- In the PR description, state: which numbers changed, the intended effect
  on difficulty, and whether a rules-version bump is needed.
- `tests/` asserts several numbers read from `data/game.json`; if you change
  a number a test pins down, update the test in the same PR and explain why.

## Art and sounds: change sources, not products

`assets/` and `sounds/` hold generated, finished files. Git cannot merge
binary files — two people editing the same PNG would silently overwrite each
other. To avoid that:

1. Never edit anything inside `assets/` or `sounds/` directly.
2. Add or change the source, then regenerate:
   ```bash
   python -m pip install pillow          # once
   python make_assets.py
   python make_sounds.py                 # standard library only
   ```
3. Commit both the source change and the regenerated files in one PR, so the
   repo stays self-consistent.
4. `raw_art/` is never changed, moved or deleted.

## Keeping main deployable

`docs/` is the live GitHub Pages build — pushing to `main` publishes it.
Treat every merged PR as a release candidate:

- The game must be playable on `main` at all times: finish features on
  branches, merge only working states.
- Only update `docs/` in a release PR, using the build steps in
  `README.md` (*Rebuild the browser version*), and rebuild from the same
  commit that is being merged.
- `main.py` must stay browser-safe: no `PIL`, `wave`, `make_assets` or
  `make_sounds` imports; pygbag constraints apply.

## Reviewing

Review can be human or AI-assisted — both are welcome. Reviewers check:

- CI green, local checks pass
- No hardcoded gameplay numbers
- No hand-edited files under `assets/` / `sounds/`; `raw_art/` untouched
- Balance changes carry a rules-version note
- UI text stays in Simplified Chinese (the whole interface is localized)

## First time here?

Welcome! Start small (a bug fix, a test, a copy fix), follow the workflow
above, and ask in an issue if you get stuck — we keep reviews friendly.

