#!/usr/bin/env python3
import re, sys, json, random
from pathlib import Path
from datetime import datetime

README_PATH = "README.md"
STATE_PATH  = ".github/ludo_state.json"
SVG_PATH    = "board.svg"

TURN_ORDER = ["red","blue","green","yellow"]
COLORS = {"red":"#D93025","blue":"#1A73E8","yellow":"#F9AB00","green":"#1E8E3E"}
LIGHT  = {"red":"#FCCFCD","blue":"#C5DCF8","yellow":"#FDE9A0","green":"#B7E1C0"}

PATH = [
    (6,1),(6,2),(6,3),(6,4),(6,5),
    (5,6),(4,6),(3,6),(2,6),(1,6),(0,6),(0,7),
    (0,8),(1,8),(2,8),(3,8),(4,8),(5,8),
    (6,9),(6,10),(6,11),(6,12),(6,13),(6,14),(7,14),
    (8,14),(8,13),(8,12),(8,11),(8,10),(8,9),
    (9,8),(10,8),(11,8),(12,8),(13,8),(14,8),(14,7),
    (14,6),(13,6),(12,6),(11,6),(10,6),(9,6),
    (8,5),(8,4),(8,3),(8,2),(8,1),(8,0),(7,0),
]
HOME_COL = {
    "red":    [(13,7),(12,7),(11,7),(10,7),(9,7)],
    "blue":   [(1,7),(2,7),(3,7),(4,7),(5,7)],
    "yellow": [(7,1),(7,2),(7,3),(7,4),(7,5)],
    "green":  [(7,13),(7,12),(7,11),(7,10),(7,9)],
}
START_IDX = {"red":34,"blue":8,"yellow":21,"green":47}
HOME_BASE = {
    "blue":   [(1,1),(1,3),(3,1),(3,3)],
    "green":  [(1,10),(1,12),(3,10),(3,12)],
    "yellow": [(10,1),(10,3),(12,1),(12,3)],
    "red":    [(10,10),(10,12),(12,10),(12,12)],
}
SAFE_IDX = {0,8,13,21,26,34,39,47}
FINISH = 100

def roll_dice():
    return random.randint(1,6)

def default_state():
    tokens = {}
    for color in TURN_ORDER:
        for i in range(1,5):
            tokens[f"{color}_{i}"] = {"color":color,"slot":i-1,"pos":-1}
    return {"turn_idx":0,"dice":roll_dice(),"tokens":tokens,
            "last_moves":[],"leaderboard":{},"game_over":False,"winner":None}

def load_state():
    p = Path(STATE_PATH)
    return json.loads(p.read_text()) if p.exists() else default_state()

def save_state(state):
    Path(STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(STATE_PATH).write_text(json.dumps(state, indent=2))

def current_color(state):
    return TURN_ORDER[state["turn_idx"]]

def token_coord(state, tid):
    t = state["tokens"][tid]
    pos, col = t["pos"], t["color"]
    if pos == FINISH: return None
    if pos == -1: return HOME_BASE[col][t["slot"]]
    hc = HOME_COL[col]
    if pos >= len(PATH):
        hi = pos - len(PATH)
        return hc[hi] if hi < len(hc) else None
    return PATH[(START_IDX[col] + pos) % len(PATH)]

def get_valid_moves(state):
    color = current_color(state)
    dice  = state["dice"]
    valid = []
    for tid, t in state["tokens"].items():
        if t["color"] != color or t["pos"] == FINISH: continue
        if t["pos"] == -1 and dice == 6:
            valid.append(tid)
        elif t["pos"] >= 0 and t["pos"]+dice <= len(PATH)+len(HOME_COL[color])-1:
            valid.append(tid)
    return valid

def advance_turn(state):
    """Move to next player, only skipping players who have fully finished."""
    state["turn_idx"] = (state["turn_idx"] + 1) % 4
    state["dice"] = roll_dice()
    # Only skip players who have ALL 4 tokens at finish
    attempts = 0
    while attempts < 4:
        color = current_color(state)
        if not all(state["tokens"][f"{color}_{i}"]["pos"] == FINISH for i in range(1,5)):
            return  # This player still has tokens to move, it's their turn
        state["turn_idx"] = (state["turn_idx"] + 1) % 4
        state["dice"] = roll_dice()
        attempts += 1

def apply_move(state, tid, author):
    t    = state["tokens"][tid]
    dice = state["dice"]
    color = t["color"]

    if t["pos"] == -1:
        t["pos"] = 0
        desc = f"{tid} entered the board"
    else:
        t["pos"] += dice
        if t["pos"] >= len(PATH) + len(HOME_COL[color]) - 1:
            t["pos"] = FINISH
            desc = f"{tid} reached the finish!"
        else:
            desc = f"{tid} moved {dice} steps"

    # Capture
    if 0 < t["pos"] < len(PATH):
        pi = (START_IDX[color] + t["pos"]) % len(PATH)
        if pi not in SAFE_IDX:
            my_rc = token_coord(state, tid)
            for oid, ot in state["tokens"].items():
                if ot["color"]==color or ot["pos"]<=0 or ot["pos"]==FINISH or ot["pos"]>=len(PATH): continue
                if token_coord(state, oid) == my_rc:
                    ot["pos"] = -1
                    desc += f", sent {oid} home"

    state["last_moves"].insert(0, {"move":desc,"author":author})
    state["last_moves"] = state["last_moves"][:5]
    state["leaderboard"][author] = state["leaderboard"].get(author,0) + 1

    # Win check
    if all(state["tokens"][f"{color}_{i}"]["pos"] == FINISH for i in range(1,5)):
        state["game_over"] = True
        state["winner"] = color
        return desc

    # Rolled 6 = take another turn (keep turn_idx, just re-roll)
    if dice == 6:
        state["dice"] = roll_dice()
        # If no valid moves even with new roll, advance anyway
        if not get_valid_moves(state):
            advance_turn(state)
    else:
        advance_turn(state)

    return desc

def render_svg(state):
    S=600; N=15; C=S/N
    def rect(x,y,w,h,fill,stroke="#333",sw=0.7):
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    def txt(x,y,s,size,fill,weight="normal"):
        return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="middle" dominant-baseline="central" font-family="sans-serif">{s}</text>'
    def rrp(x,y,w,h,r):
        return f"M{x+r},{y} L{x+w-r},{y} Q{x+w},{y} {x+w},{y+r} L{x+w},{y+h-r} Q{x+w},{y+h} {x+w-r},{y+h} L{x+r},{y+h} Q{x},{y+h} {x},{y+h-r} L{x},{y+r} Q{x},{y} {x+r},{y} Z"
    p = [f'<svg width="{S}" height="{S}" viewBox="0 0 {S} {S}" xmlns="http://www.w3.org/2000/svg">']
    p.append(f'<rect width="{S}" height="{S}" fill="#fff"/>')
    for color,br,bc in [("blue",0,0),("green",0,9),("yellow",9,0),("red",9,9)]:
        p.append(rect(bc*C,br*C,6*C,6*C,COLORS[color]))
        for dr,dc in [(1,1),(1,3),(3,1),(3,3)]:
            x,y,s=(bc+dc)*C+4,(br+dr)*C+4,C*2-8
            p.append(f'<path d="{rrp(x,y,s,s,6)}" fill="#fff" stroke="#333" stroke-width="1"/>')
    for r in range(N):
        for c in range(6,9): p.append(rect(c*C,r*C,C,C,"#fff"))
    for r in range(6,9):
        for c in range(N): p.append(rect(c*C,r*C,C,C,"#fff"))
    for r in range(1,6):  p.append(rect(7*C,r*C,C,C,LIGHT["blue"]))
    for r in range(9,14): p.append(rect(7*C,r*C,C,C,LIGHT["red"]))
    for c in range(1,6):  p.append(rect(c*C,7*C,C,C,LIGHT["yellow"]))
    for c in range(9,14): p.append(rect(c*C,7*C,C,C,LIGHT["green"]))
    p.append(rect(1*C,6*C,C,C,LIGHT["yellow"]))
    p.append(rect(8*C,2*C,C,C,LIGHT["blue"]))
    p.append(rect(13*C,8*C,C,C,LIGHT["green"]))
    p.append(rect(6*C,12*C,C,C,LIGHT["red"]))
    cx,cy,cs=6*C,6*C,3*C
    for fill,pts in [(COLORS["blue"],[(cx+cs/2,cy+cs/2),(cx,cy),(cx+cs,cy)]),
                     (COLORS["green"],[(cx+cs/2,cy+cs/2),(cx+cs,cy),(cx+cs,cy+cs)]),
                     (COLORS["red"],[(cx+cs/2,cy+cs/2),(cx+cs,cy+cs),(cx,cy+cs)]),
                     (COLORS["yellow"],[(cx+cs/2,cy+cs/2),(cx,cy+cs),(cx,cy)])]:
        ps=" ".join(f"{px:.1f},{py:.1f}" for px,py in pts)
        p.append(f'<polygon points="{ps}" fill="{fill}"/>')
    p.append(f'<rect x="{cx}" y="{cy}" width="{cs}" height="{cs}" fill="none" stroke="#333" stroke-width="1"/>')
    p.append(f'<line x1="{cx}" y1="{cy}" x2="{cx+cs}" y2="{cy+cs}" stroke="#333" stroke-width="1"/>')
    p.append(f'<line x1="{cx+cs}" y1="{cy}" x2="{cx}" y2="{cy+cs}" stroke="#333" stroke-width="1"/>')
    for r in range(N+1):
        p.append(f'<line x1="0" y1="{r*C:.1f}" x2="{S}" y2="{r*C:.1f}" stroke="#ccc" stroke-width="0.4"/>')
    for c in range(N+1):
        p.append(f'<line x1="{c*C:.1f}" y1="0" x2="{c*C:.1f}" y2="{S}" stroke="#ccc" stroke-width="0.4"/>')
    for i,(r,c) in enumerate(PATH):
        if i in SAFE_IDX:
            p.append(txt(c*C+C/2,r*C+C/2,"★",C*0.4,"rgba(0,0,0,0.2)"))
    valid = get_valid_moves(state) if not state["game_over"] else []
    for tid,t in state["tokens"].items():
        coord=token_coord(state,tid)
        if coord is None: continue
        r,c=coord; tx,ty=c*C+C/2,r*C+C/2; rad=C*0.33; col=COLORS[t["color"]]
        if tid in valid:
            p.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{rad+5:.1f}" fill="rgba(239,159,39,0.55)"/>')
        p.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{rad:.1f}" fill="{col}" stroke="rgba(0,0,0,0.3)" stroke-width="1.5"/>')
        p.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{rad*0.62:.1f}" fill="rgba(255,255,255,0.88)"/>')
        p.append(txt(tx,ty,str(t["slot"]+1),C*0.26,col,"bold"))
    turn_color=current_color(state)
    if state["game_over"]:
        banner=f"{state['winner'].capitalize()} wins!"; bc=COLORS.get(state["winner"],"#333")
    else:
        banner=f"{turn_color.capitalize()}'s turn  |  Rolled: {state['dice']}"; bc=COLORS[turn_color]
    p.append(f'<rect x="0" y="{S-28}" width="{S}" height="28" fill="{bc}" opacity="0.9"/>')
    p.append(txt(S/2,S-14,banner,13,"#fff","bold"))
    p.append('</svg>')
    return "\n".join(p)

def replace_section(content,begin_tag,end_tag,new_content):
    pattern=rf"(<!-- {re.escape(begin_tag)} -->).*?(<!-- {re.escape(end_tag)} -->)"
    return re.sub(pattern,rf"\1\n{new_content}\n\2",content,flags=re.DOTALL)

def render_moves_list(state):
    if state["game_over"]: return f"| — | {state['winner'].capitalize()} wins! |"
    valid=get_valid_moves(state); color=current_color(state); dice=state["dice"]
    base="https://github.com/noorimtiaz2004/noorimtiaz2004/issues/new"
    body="body=Please+do+not+change+the+title.+Just+click+%22Submit+new+issue%22."
    lines=["| Token | Move |","|:-----:|:-----|"]
    for tid in [f"{color}_{i}" for i in range(1,5)]:
        t=state["tokens"][tid]
        if tid in valid:
            label=f"Token {t['slot']+1} — exit home!" if t["pos"]==-1 else f"Token {t['slot']+1} — move {dice} steps"
            title=f"Ludo%3A+Move+{tid}"
            lines.append(f"| **{tid}** | [{label}]({base}?{body}&title={title}) |")
        else:
            lines.append(f"| ~~{tid}~~ | *Can't move* |")
    return "\n".join(lines)

def render_token_status(state):
    headers="|".join(f" {c}_{i} " for c in TURN_ORDER for i in range(1,5))
    seps="|".join(":--:" for _ in range(16))
    def fmt(pos):
        if pos==-1: return "🏠"
        if pos==FINISH: return "✅"
        return str(pos)
    vals="|".join(fmt(state["tokens"][f"{c}_{i}"]["pos"]) for c in TURN_ORDER for i in range(1,5))
    return f"| Token |{headers}|\n|:-----:|{seps}|\n| Position |{vals}|"

def render_last_moves(state):
    if not state["last_moves"]: return "| *No moves yet!* | — |"
    lines=["| Move | Author |","|:----:|:-------|"]
    for m in state["last_moves"]:
        lines.append(f"| `{m['move']}` | [@{m['author']}](https://github.com/{m['author']}) |")
    return "\n".join(lines)

def render_leaderboard(state):
    lb=state["leaderboard"]
    if not lb: return "| *No moves yet!* | — |"
    lines=["| Total moves | User |","|:-----------:|:-----|"]
    for user,count in sorted(lb.items(),key=lambda x:x[1],reverse=True)[:10]:
        lines.append(f"| {count} | [@{user}](https://github.com/{user}) |")
    return "\n".join(lines)

def update_readme(state):
    content=Path(README_PATH).read_text(encoding="utf-8")
    content=replace_section(content,"BEGIN TURN","END TURN",current_color(state).capitalize())
    content=replace_section(content,"BEGIN DICE ROLL","END DICE ROLL",str(state["dice"]))
    content=replace_section(content,"BEGIN LUDO BOARD","END LUDO BOARD","![Ludo Board](board.svg)")
    content=replace_section(content,"BEGIN TOKEN STATUS","END TOKEN STATUS",render_token_status(state))
    content=replace_section(content,"BEGIN MOVES LIST","END MOVES LIST",render_moves_list(state))
    content=replace_section(content,"BEGIN LAST MOVES","END LAST MOVES",render_last_moves(state))
    content=replace_section(content,"BEGIN TOP MOVES","END TOP MOVES",render_leaderboard(state))
    Path(README_PATH).write_text(content,encoding="utf-8")

def main():
    if len(sys.argv)<3: print("Usage: python3 ludo.py <token_id> <username>"); sys.exit(1)
    tid,author=sys.argv[1].lower(),sys.argv[2]
    state=load_state()
    if state["game_over"]: print("Game over!"); sys.exit(0)
    color=current_color(state)
    if not tid.startswith(color): print(f"Error: It's {color}'s turn."); sys.exit(1)
    if tid not in get_valid_moves(state):
        print(f"Error: {tid} cannot move (dice={state['dice']}).")
        sys.exit(1)
    desc=apply_move(state,tid,author)
    print(f"Move: {desc}")
    save_state(state)
    Path(SVG_PATH).write_text(render_svg(state),encoding="utf-8")
    update_readme(state)
    print(f"Done. Next turn: {current_color(state)}, dice: {state['dice']}")

if __name__=="__main__":
    main()
