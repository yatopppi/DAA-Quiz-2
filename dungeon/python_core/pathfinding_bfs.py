"""
pathfinding_bfs.py
==================
Pathfinding musuh menggunakan Breadth-First Search (BFS).

Mengapa BFS (bukan DFS atau Dijkstra)?
- BFS menjamin jalur TERPENDEK pada graf tak berbobot (tiap langkah = biaya 1)
- Maze dungeon adalah graf tak berbobot → BFS adalah pilihan optimal
- Dijkstra tidak diperlukan karena semua edge memiliki bobot sama
- DFS tidak menjamin jalur terpendek

Kompleksitas:
- Waktu  : O(V + E) di mana V = sel, E = koneksi antar sel
- Memori : O(V) untuk queue, visited, dan parent map
"""

from collections import deque
from typing import List, Tuple, Optional, Set

WALL  = 0
FLOOR = 1

# 4 arah gerak: atas, bawah, kiri, kanan
DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def bfs_path(
    grid: List[List[int]],
    start: Tuple[int, int],
    goal: Tuple[int, int],
    blocked: Set[Tuple[int, int]] = None
) -> List[Tuple[int, int]]:
    """
    Cari jalur terpendek dari start ke goal menggunakan BFS.

    Parameter:
        grid    : 2D grid maze (WALL/FLOOR)
        start   : posisi awal (row, col)
        goal    : posisi tujuan (row, col)
        blocked : set posisi yang tidak boleh dilewati (posisi musuh lain)

    Return:
        List posisi dari start+1 hingga goal (tidak termasuk start itu sendiri).
        List kosong jika tidak ada jalur.

    Cara kerja BFS langkah demi langkah:
        1. Masukkan start ke dalam queue dan visited
        2. Selama queue tidak kosong:
           a. Ambil sel terdepan (FIFO — inilah yang membuat BFS berbeda dari DFS)
           b. Jika sel ini adalah goal → rekonstruksi jalur dari parent map
           c. Untuk setiap tetangga valid (FLOOR, tidak visited, tidak blocked):
              - Tandai sebagai visited
              - Catat parent-nya (dari sel mana kita datang)
              - Masukkan ke queue
        3. Jika queue habis tanpa menemukan goal → tidak ada jalur
    """
    if blocked is None:
        blocked = set()

    rows = len(grid)
    cols = len(grid[0])
    sr, sc = start
    gr, gc = goal

    # Edge case: sudah di tujuan
    if start == goal:
        return []

    # --- LANGKAH 1: Inisialisasi BFS ---
    # deque digunakan bukan list biasa karena popleft() = O(1)
    # list.pop(0) = O(n) yang jauh lebih lambat
    queue = deque()
    queue.append((sr, sc))

    visited = set()
    visited.add((sr, sc))

    # parent[sel] = sel dari mana kita datang
    # Digunakan untuk merekonstruksi jalur di akhir
    parent = {(sr, sc): None}

    # --- LANGKAH 2: Loop BFS ---
    while queue:
        # 2a. Ambil dari DEPAN queue (FIFO) → BFS level-by-level
        r, c = queue.popleft()

        # 2b. Cek apakah sudah sampai goal
        if (r, c) == (gr, gc):
            return _reconstruct_path(parent, start, goal)

        # 2c. Eksplorasi tetangga
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc

            # Validasi batas grid
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue

            # Skip tembok
            if grid[nr][nc] == WALL:
                continue

            # Skip yang sudah dikunjungi
            if (nr, nc) in visited:
                continue

            # Skip sel yang diblokir musuh lain
            # (kecuali itu adalah goal/pemain)
            if (nr, nc) in blocked and (nr, nc) != goal:
                continue

            visited.add((nr, nc))
            parent[(nr, nc)] = (r, c)
            queue.append((nr, nc))

    # Tidak ada jalur ditemukan
    return []


def _reconstruct_path(
    parent: dict,
    start: Tuple[int, int],
    goal: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """
    Rekonstruksi jalur dari goal kembali ke start menggunakan parent map.

    Cara kerja:
    - Mulai dari goal, telusuri parent hingga mencapai start
    - Karena penelusuran mundur, balik path di akhir
    - Kembalikan path tanpa menyertakan start itu sendiri
    """
    path = []
    current = goal
    while current != start:
        path.append(current)
        current = parent[current]
    path.reverse()  # balik dari [goal→start] menjadi [start+1→goal]
    return path


def bfs_distance(
    grid: List[List[int]],
    start: Tuple[int, int],
    goal: Tuple[int, int]
) -> int:
    """
    Hitung jarak terpendek (jumlah langkah) antara dua titik.
    Return -1 jika tidak ada jalur.
    """
    path = bfs_path(grid, start, goal)
    if not path and start != goal:
        return -1
    return len(path)


def bfs_reachable(
    grid: List[List[int]],
    start: Tuple[int, int]
) -> Set[Tuple[int, int]]:
    """
    Temukan semua sel yang dapat dijangkau dari start.
    Digunakan untuk flood-fill (cek konektivitas maze).
    """
    rows, cols = len(grid), len(grid[0])
    visited = set()
    queue = deque([start])
    visited.add(start)

    while queue:
        r, c = queue.popleft()
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols and
                    grid[nr][nc] == FLOOR and
                    (nr, nc) not in visited):
                visited.add((nr, nc))
                queue.append((nr, nc))

    return visited


# ── Demo standalone ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    from maze_prim import generate_maze, print_maze, WALL, FLOOR

    print("=== BFS PATHFINDING DEMO ===\n")
    maze = generate_maze(11, 11, seed=42)

    # Pilih titik awal dan tujuan
    start = (1, 1)
    goal  = (9, 9)

    path = bfs_path(maze, start, goal)
    dist = bfs_distance(maze, start, goal)

    print(f"Dari {start} ke {goal}")
    print(f"Panjang jalur: {dist} langkah")
    print(f"Jalur: {path[:5]}{'...' if len(path)>5 else ''}\n")

    # Visualisasi path di maze
    path_set = set(path)
    symbols = {WALL: '██', FLOOR: '  '}
    for r, row in enumerate(maze):
        line = ''
        for c, cell in enumerate(row):
            if (r, c) == start:
                line += 'SS'
            elif (r, c) == goal:
                line += 'GG'
            elif (r, c) in path_set:
                line += '··'
            else:
                line += symbols[cell]
        print(line)

    print(f"\nLegenda: SS=Start  GG=Goal  ··=Jalur BFS")
