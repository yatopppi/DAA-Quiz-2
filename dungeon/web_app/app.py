"""
app.py
======
Flask web server — jembatan antara Python game engine dan browser.

Arsitektur:
    Browser (HTML/JS)
        ↕  HTTP JSON (fetch API)
    Flask (app.py)        ← file ini
        ↕  import Python
    Game Engine (game_engine.py)
        ↕  import Python
    maze_prim.py + pathfinding_bfs.py

Cara Flask bekerja:
- @app.route('/path') mendaftarkan fungsi sebagai "handler" untuk URL tertentu
- request.json membaca body JSON dari browser
- jsonify() mengubah dict Python menjadi JSON response
- Session disimpan di memori (dict global) — untuk produksi, gunakan Redis/DB

Endpoint:
    POST /api/new_game          → mulai game baru
    POST /api/action            → kirim aksi player (move/wait)
    GET  /                      → serve index.html
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python_core'))

from flask import Flask, request, jsonify, send_from_directory
from game_engine import new_game, move_player, wait_turn, _serialize

app = Flask(__name__, static_folder='static')

# ── Session Storage (in-memory) ───────────────────────────────────────────────
# Dalam produksi nyata, ganti dengan database atau Redis
# Key: session_id (string), Value: GameState object
game_sessions: dict = {}
SESSION_ID = "default"  # single-player sederhana


# ── Route: Serve Frontend ─────────────────────────────────────────────────────

@app.route('/')
def index():
    """
    Serve file index.html ke browser.
    Flask mencari file di folder 'static/' secara default.
    """
    return send_from_directory('static', 'index.html')


# ── Route: New Game ───────────────────────────────────────────────────────────

@app.route('/api/new_game', methods=['POST'])
def api_new_game():
    """
    Endpoint untuk memulai game baru.

    Cara kerja:
    1. Panggil new_game() dari game_engine.py
    2. Simpan GameState di memori server (game_sessions)
    3. Kembalikan state awal ke browser sebagai JSON

    Browser menerima seluruh state (grid, fog, posisi entitas)
    dan menggambar ulang canvas dari data tersebut.
    """
    state = new_game()
    game_sessions[SESSION_ID] = state

    return jsonify({
        "ok": True,
        "state": _serialize(state)
    })


# ── Route: Player Action ──────────────────────────────────────────────────────

@app.route('/api/action', methods=['POST'])
def api_action():
    """
    Endpoint untuk semua aksi player.

    Body JSON yang diterima:
        { "type": "move", "dr": -1, "dc": 0 }   → gerak ke atas
        { "type": "move", "dr":  1, "dc": 0 }   → gerak ke bawah
        { "type": "move", "dr":  0, "dc": -1 }  → gerak ke kiri
        { "type": "move", "dr":  0, "dc":  1 }  → gerak ke kanan
        { "type": "wait" }                        → tunggu giliran

    Flow:
    1. Ambil GameState dari memori
    2. Panggil fungsi engine yang sesuai
    3. Engine mengupdate state (player, musuh, fog, log)
    4. Kembalikan state terbaru ke browser

    Pendekatan ini disebut "server-authoritative":
    semua logika game ada di server (Python), browser hanya render.
    Ini mencegah cheating di game multiplayer.
    """
    state = game_sessions.get(SESSION_ID)
    if state is None:
        return jsonify({"ok": False, "error": "No active game. Call /api/new_game first."}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid JSON body."}), 400

    action_type = data.get("type")

    if action_type == "move":
        try:
            dr = int(data.get("dr", 0))
            dc = int(data.get("dc", 0))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Move delta must be an integer."}), 400
        result = move_player(state, dr, dc)

    elif action_type == "wait":
        result = wait_turn(state)

    else:
        return jsonify({"ok": False, "error": f"Unknown action: {action_type}"}), 400

    return jsonify(result)


# ── Route: Debug Info ─────────────────────────────────────────────────────────

@app.route('/api/debug', methods=['GET'])
def api_debug():
    """
    Endpoint debug — lihat state game mentah.
    Berguna saat development untuk memverifikasi data.
    """
    state = game_sessions.get(SESSION_ID)
    if state is None:
        return jsonify({"error": "No game session"})

    return jsonify({
        "floor": state.floor,
        "player_pos": [state.player.r, state.player.c],
        "player_hp": state.player.hp,
        "num_enemies": len(state.enemies),
        "num_health_packs": len(state.health_packs),
        "exit_pos": list(state.exit_pos),
        "enemies": [{"id": e.id, "pos": [e.r, e.c], "hp": e.hp}
                    for e in state.enemies],
        "health_packs": [{"pos": [r, c]} for r, c in state.health_packs]
    })


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 50)
    print("  DUNGEON DESCENT — Flask Server")
    print("=" * 50)
    print("  Buka browser: http://localhost:5000")
    print("  Debug API  : http://localhost:5000/api/debug")
    print("  Stop server: Ctrl+C")
    print("=" * 50)

    # debug=True → auto-reload saat file diubah (jangan pakai di produksi)
    app.run(debug=True, port=5000)
