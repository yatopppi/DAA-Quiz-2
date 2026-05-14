"""
game_engine.py
==============
Logika permainan murni — tanpa UI, tanpa rendering.

File ini adalah "otak" game yang dapat dijalankan standalone di terminal
maupun diimpor oleh web app (Flask). Semua keputusan game ada di sini.

Prinsip desain:
- Tidak ada import library UI (pygame, tkinter, dll.)
- Semua state tersimpan dalam objek GameState
- Semua aksi mengembalikan dict hasil yang bisa dikirim ke frontend manapun
"""

import random
import json
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict, Any, Optional

from maze_prim import generate_maze, get_floor_cells, WALL, FLOOR
from pathfinding_bfs import bfs_path, bfs_reachable

# ── Konstanta game ────────────────────────────────────────────────────────────
ROWS        = 21
COLS        = 21
TOTAL_FLOORS = 3
VISION_RADIUS = 4
FOG_HIDDEN  = 0
FOG_SEEN    = 1
FOG_VISIBLE = 2
HEALTH_HEAL = 25
HEALTH_PACKS_BASE = 2


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class Player:
    r: int
    c: int
    hp: int      = 100
    max_hp: int  = 100
    atk_min: int = 8
    atk_max: int = 12
    kills: int   = 0
    steps: int   = 0


@dataclass
class Enemy:
    id: int
    r: int
    c: int
    hp: int
    max_hp: int
    atk_min: int
    atk_max: int
    aggro_range: int = 8  # jarak maksimal sebelum mulai mengejar


@dataclass
class GameState:
    floor: int
    total_kills: int
    total_steps: int
    player: Player
    enemies: List[Enemy]
    health_packs: List[Tuple[int, int]]
    grid: List[List[int]]      # WALL / FLOOR
    fog: List[List[int]]       # FOG_HIDDEN / FOG_SEEN / FOG_VISIBLE
    exit_pos: Tuple[int, int]
    log: List[Dict]            # riwayat pesan game
    active: bool = True
    won: bool    = False


# ── Engine Functions ──────────────────────────────────────────────────────────

def new_game() -> GameState:
    """Buat game baru dari awal."""
    player = Player(r=1, c=1)
    state = GameState(
        floor=1,
        total_kills=0,
        total_steps=0,
        player=player,
        enemies=[],
        health_packs=[],
        grid=[],
        fog=[],
        exit_pos=(0, 0),
        log=[]
    )
    _init_level(state)
    _add_log(state, f"Kamu memasuki Lantai 1. Waspadalah!", "good")
    _add_log(state, "Musuh menggunakan BFS untuk mengejar kamu.", "info")
    return state


def move_player(state: GameState, dr: int, dc: int) -> Dict[str, Any]:
    """
    Gerakkan player ke arah (dr, dc).

    Return:
        dict berisi hasil aksi: apakah berhasil, log baru, dll.
    """
    if not state.active:
        return {"ok": False, "reason": "game_over"}

    if abs(dr) + abs(dc) != 1:
        return {"ok": False, "reason": "invalid_move"}

    nr = state.player.r + dr
    nc = state.player.c + dc

    # Cek batas grid
    if not (0 <= nr < ROWS and 0 <= nc < COLS):
        return {"ok": False, "reason": "out_of_bounds"}

    # Cek tembok
    if state.grid[nr][nc] == WALL:
        return {"ok": False, "reason": "wall"}

    # Cek musuh di target → serang
    enemy = _enemy_at(state, nr, nc)
    if enemy:
        _player_attack(state, enemy)
    else:
        # Bergerak
        state.player.r = nr
        state.player.c = nc
        state.player.steps += 1
        state.total_steps += 1
        _collect_health_pack(state, nr, nc)

        # Cek apakah sampai di exit
        if (nr, nc) == state.exit_pos:
            return _handle_exit(state)

    # Update fog of war
    _update_fog(state)

    # Giliran musuh
    _enemy_turn(state)

    return {"ok": True, "state": _serialize(state)}


def wait_turn(state: GameState) -> Dict[str, Any]:
    """Lewati giliran player (musuh tetap bergerak)."""
    if not state.active:
        return {"ok": False}
    state.player.steps += 1
    state.total_steps += 1
    _update_fog(state)
    _enemy_turn(state)
    return {"ok": True, "state": _serialize(state)}


# ── Level Management ──────────────────────────────────────────────────────────

def _init_level(state: GameState):
    """Buat lantai baru: generate maze, tempatkan entitas."""
    state.grid = generate_maze(ROWS, COLS)
    state.fog  = [[FOG_HIDDEN] * COLS for _ in range(ROWS)]

    # Semua sel lantai yang bisa dijangkau dari (1,1)
    reachable = list(bfs_reachable(state.grid, (1, 1)))
    reachable.sort()  # deterministik

    def pick_far(min_dist: int) -> Tuple[int, int]:
        """Pilih sel acak yang jaraknya > min_dist dari (1,1)."""
        candidates = [
            (r, c) for r, c in reachable
            if abs(r - 1) + abs(c - 1) >= min_dist
        ]
        if not candidates:
            candidates = reachable
        return random.choice(candidates)

    # Tempatkan player di (1,1)
    state.player.r = 1
    state.player.c = 1

    # Tempatkan exit jauh dari player
    er, ec = pick_far(10)
    state.exit_pos = (er, ec)

    # Tempatkan musuh (jumlah bertambah per lantai)
    num_enemies = 3 + state.floor
    state.enemies = []
    state.health_packs = []
    occupied = {(1, 1), (er, ec)}

    for i in range(num_enemies):
        for _ in range(50):  # max attempts
            r, c = random.choice(reachable)
            if (r, c) not in occupied and abs(r-1)+abs(c-1) >= 5:
                hp = 20 + state.floor * 5
                state.enemies.append(Enemy(
                    id=i, r=r, c=c,
                    hp=hp, max_hp=hp,
                    atk_min=3 + state.floor,
                    atk_max=6 + state.floor
                ))
                occupied.add((r, c))
                break

    # Tempatkan darah/health pack di sel lantai yang tersebar.
    # Jumlahnya sedikit bertambah per lantai agar lantai yang lebih sulit
    # tetap punya peluang pemulihan.
    num_health_packs = HEALTH_PACKS_BASE + state.floor
    for _ in range(num_health_packs):
        for _ in range(50):
            r, c = random.choice(reachable)
            if (r, c) not in occupied and abs(r-1)+abs(c-1) >= 4:
                state.health_packs.append((r, c))
                occupied.add((r, c))
                break

    _update_fog(state)


# ── Combat ────────────────────────────────────────────────────────────────────

def _player_attack(state: GameState, enemy: Enemy):
    """Player menyerang musuh."""
    dmg = random.randint(state.player.atk_min, state.player.atk_max)
    enemy.hp -= dmg
    _add_log(state, f"Kamu menyerang musuh #{enemy.id}! -{dmg} HP", "combat")

    if enemy.hp <= 0:
        state.enemies = [e for e in state.enemies if e.id != enemy.id]
        state.player.kills += 1
        state.total_kills += 1
        _add_log(state, f"Musuh #{enemy.id} mati!", "good")


def _enemy_turn(state: GameState):
    """
    Semua musuh bergerak/menyerang menggunakan BFS.

    Setiap musuh:
    1. Hitung jarak Manhattan ke player
    2. Jika berdekatan (jarak=1) → serang
    3. Jika dalam aggro_range → jalankan BFS, gerak ke langkah pertama jalur
    4. Jika terlalu jauh → diam
    """
    if not state.active:
        return

    # Posisi semua musuh (sebagai "blocked" agar tidak saling menempati)
    blocked = {(e.r, e.c) for e in state.enemies}

    for enemy in state.enemies[:]:  # slice copy karena list bisa berubah
        pr, pc = state.player.r, state.player.c
        dist = abs(enemy.r - pr) + abs(enemy.c - pc)

        if dist <= 1:
            # ── Serang player ──
            dmg = random.randint(enemy.atk_min, enemy.atk_max)
            state.player.hp -= dmg
            _add_log(state, f"Musuh #{enemy.id} menyerang! -{dmg} HP", "combat")

            if state.player.hp <= 0:
                state.player.hp = 0
                state.active = False
                state.won = False
                _add_log(state, "Kamu gugur di kegelapan...", "danger")
                return

        elif dist <= enemy.aggro_range:
            # ── BFS Pathfinding ──
            # Keluarkan posisi musuh ini sendiri dari blocked set
            other_blocked = blocked - {(enemy.r, enemy.c)}
            path = bfs_path(
                state.grid,
                (enemy.r, enemy.c),
                (pr, pc),
                other_blocked
            )
            if path:
                nr, nc = path[0]  # langkah pertama jalur terpendek
                # Pastikan tidak menempati musuh lain
                if (nr, nc) not in other_blocked:
                    blocked.discard((enemy.r, enemy.c))
                    enemy.r = nr
                    enemy.c = nc
                    blocked.add((nr, nc))


# ── Exit / Floor Transition ───────────────────────────────────────────────────

def _handle_exit(state: GameState) -> Dict[str, Any]:
    """Handle player menyentuh exit tile."""
    if state.floor >= TOTAL_FLOORS:
        # Menang!
        state.active = False
        state.won = True
        _add_log(state, "Kamu berhasil keluar dari dungeon! MENANG!", "gold")
        return {"ok": True, "event": "win", "state": _serialize(state)}

    # Naik ke lantai berikutnya
    state.floor += 1
    heal = 20
    state.player.hp = min(state.player.max_hp, state.player.hp + heal)
    state.player.atk_min += 1
    state.player.atk_max += 2
    _init_level(state)
    _add_log(state, f"Lantai {state.floor}! +{heal} HP. ATK meningkat!", "gold")
    return {"ok": True, "event": "next_floor", "state": _serialize(state)}


# ── Fog of War ────────────────────────────────────────────────────────────────

def _update_fog(state: GameState):
    """
    Update visibility berdasarkan posisi player.
    Menggunakan raycast Bresenham sederhana dalam radius VISION_RADIUS.
    """
    pr, pc = state.player.r, state.player.c

    # Reset sel yang sebelumnya VISIBLE → SEEN
    for r in range(ROWS):
        for c in range(COLS):
            if state.fog[r][c] == FOG_VISIBLE:
                state.fog[r][c] = FOG_SEEN

    # Tandai sel dalam radius sebagai VISIBLE jika ada LOS
    r2 = VISION_RADIUS * VISION_RADIUS
    for dr in range(-VISION_RADIUS, VISION_RADIUS + 1):
        for dc in range(-VISION_RADIUS, VISION_RADIUS + 1):
            if dr * dr + dc * dc > r2:
                continue
            r, c = pr + dr, pc + dc
            if 0 <= r < ROWS and 0 <= c < COLS:
                if _has_los(state.grid, pr, pc, r, c):
                    state.fog[r][c] = FOG_VISIBLE


def _has_los(grid, r0, c0, r1, c1) -> bool:
    """Bresenham line-of-sight check."""
    x, y = c0, r0
    dx, dy = abs(c1 - c0), abs(r1 - r0)
    sx = 1 if c0 < c1 else -1
    sy = 1 if r0 < r1 else -1
    err = dx - dy
    while True:
        if x == c1 and y == r1:
            return True
        if grid[y][x] == WALL and not (x == c0 and y == r0):
            return False
        e2 = 2 * err
        if e2 > -dy:
            err -= dy; x += sx
        if e2 < dx:
            err += dx; y += sy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enemy_at(state: GameState, r: int, c: int) -> Optional[Enemy]:
    """Cari musuh di posisi (r, c)."""
    for e in state.enemies:
        if e.r == r and e.c == c:
            return e
    return None


def _collect_health_pack(state: GameState, r: int, c: int):
    """Pulihkan HP saat player menginjak health pack."""
    pos = (r, c)
    if pos not in state.health_packs:
        return

    state.health_packs.remove(pos)
    before = state.player.hp
    state.player.hp = min(state.player.max_hp, state.player.hp + HEALTH_HEAL)
    healed = state.player.hp - before

    if healed > 0:
        _add_log(state, f"Kamu mengambil darah. +{healed} HP", "good")
    else:
        _add_log(state, "Kamu mengambil darah, tapi HP sudah penuh.", "info")


def _add_log(state: GameState, msg: str, type_: str = ""):
    """Tambah entri ke log game (max 20 entri)."""
    state.log.insert(0, {"msg": msg, "type": type_})
    if len(state.log) > 20:
        state.log.pop()


def _serialize(state: GameState) -> Dict:
    """
    Konversi GameState ke dict JSON-serializable.
    Digunakan untuk mengirim state ke frontend.
    """
    return {
        "floor":        state.floor,
        "total_floors": TOTAL_FLOORS,
        "total_kills":  state.total_kills,
        "total_steps":  state.total_steps,
        "active":       state.active,
        "won":          state.won,
        "player": {
            "r": state.player.r, "c": state.player.c,
            "hp": state.player.hp, "max_hp": state.player.max_hp,
            "atk_min": state.player.atk_min, "atk_max": state.player.atk_max,
            "kills": state.player.kills, "steps": state.player.steps,
        },
        "enemies": [
            {"id": e.id, "r": e.r, "c": e.c,
             "hp": e.hp, "max_hp": e.max_hp}
            for e in state.enemies
        ],
        "health_packs": [
            {"r": r, "c": c, "heal": HEALTH_HEAL}
            for r, c in state.health_packs
        ],
        "grid":     state.grid,
        "fog":      state.fog,
        "exit_pos": list(state.exit_pos),
        "log":      state.log[:8],
    }


# ── Terminal demo ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=== GAME ENGINE DEMO (Terminal) ===\n")

    state = new_game()

    def show(state):
        p = state.player
        print(f"\nLantai {state.floor} | HP: {p.hp}/{p.max_hp} | "
              f"Pos: ({p.r},{p.c}) | Musuh: {len(state.enemies)}")
        # Render mini-map
        grid = state.grid
        fog  = state.fog
        for r in range(ROWS):
            row_str = ''
            for c in range(COLS):
                if fog[r][c] == FOG_HIDDEN:
                    row_str += '  '
                elif (r,c) == (state.player.r, state.player.c):
                    row_str += '@·'
                elif (r,c) == state.exit_pos:
                    row_str += '▼·'
                elif (r,c) in state.health_packs:
                    row_str += '+·'
                elif any(e.r==r and e.c==c for e in state.enemies):
                    row_str += 'E·'
                elif grid[r][c] == WALL:
                    row_str += '██'
                else:
                    row_str += '··'
            print(row_str)

    show(state)

    # Simulasi beberapa gerakan
    moves = [(0,1),(0,1),(1,0),(1,0),(0,1),(0,1),(1,0)]
    for dr, dc in moves:
        result = move_player(state, dr, dc)
        if not state.active:
            break

    print("\n--- Setelah beberapa gerakan ---")
    show(state)
    print("\nLog terbaru:")
    for entry in state.log[:5]:
        print(f"  [{entry['type']:6}] {entry['msg']}")
