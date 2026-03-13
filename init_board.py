#!/usr/bin/env python3
"""
Run this once locally to generate the initial board.svg and ludo_state.json.
  python init_board.py
"""
import json
from pathlib import Path
from ludo import default_state, render_svg, save_state, STATE_PATH, SVG_PATH

state = default_state()
save_state(state)
Path(SVG_PATH).write_text(render_svg(state), encoding="utf-8")
print(f"Created {SVG_PATH} and {STATE_PATH}")
print("Commit both files to your repo to start the game!")
