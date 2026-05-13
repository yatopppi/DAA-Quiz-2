"""
maze_prim.py
============
Maze generation menggunakan Algoritma Prim (Randomized Prim's Algorithm).

Konsep:
- Grid direpresentasikan sebagai 2D list dengan nilai WALL (0) dan FLOOR (1)
- Grid harus berukuran ganjil (e.g. 21x21) agar sel-sel "kamar" berada
  di posisi genap dan "tembok" di posisi ganjil
- Algoritma Prim versi maze membangun Minimum Spanning Tree secara acak
  dengan memilih frontier secara random (bukan berdasarkan bobot)

Kompleksitas:
- Waktu  : O(V) di mana V = jumlah sel lantai
- Memori : O(V) untuk menyimpan set frontier dan parent
"""

import random
from typing import List, Tuple

# Konstanta tipe sel
WALL  = 0
FLOOR = 1


def generate_maze(rows: int, cols: int, seed: int = None) -> List[List[int]]:
    """
    Buat maze dengan Randomized Prim's Algorithm.

    Parameter:
        rows  : jumlah baris grid (harus ganjil, min 5)
        cols  : jumlah kolom grid (harus ganjil, min 5)
        seed  : opsional, untuk hasil deterministik (testing)

    Return:
        grid 2D list berisi WALL (0) dan FLOOR (1)

    Cara kerja langkah demi langkah:
        1. Inisialisasi seluruh grid sebagai WALL
        2. Pilih sel awal (1,1) → jadikan FLOOR, tandai sebagai "in_maze"
        3. Tambahkan semua tetangga 2-langkah dari (1,1) ke daftar frontier
        4. Loop selama frontier tidak kosong:
           a. Pilih satu sel frontier secara ACAK  ← inilah "randomized" Prim
           b. Cari tetangga 2-langkah yang sudah in_maze
           c. Jika ada → hancurkan tembok di antara keduanya (buat FLOOR)
              dan tandai sel frontier sebagai in_maze
           d. Tambahkan tetangga baru ke frontier
        5. Hasil: maze sempurna (setiap sel terhubung tepat satu jalur)
    """
    if seed is not None:
        random.seed(seed)

    # Validasi ukuran
    assert rows >= 5 and rows % 2 == 1, "rows harus ganjil dan >= 5"
    assert cols >= 5 and cols % 2 == 1, "cols harus ganjil dan >= 5"

    # --- LANGKAH 1: Inisialisasi semua sel sebagai WALL ---
    grid = [[WALL] * cols for _ in range(rows)]

    # Set untuk melacak sel yang sudah menjadi bagian maze
    in_maze = set()

    # --- LANGKAH 2: Sel awal ---
    start_r, start_c = 1, 1
    grid[start_r][start_c] = FLOOR
    in_maze.add((start_r, start_c))

    # --- LANGKAH 3: Tambahkan frontier awal ---
    frontier: List[Tuple[int, int]] = []
    frontier_set = set()  # untuk mengecek duplikat O(1)

    def add_frontier(r: int, c: int):
        """Tambahkan sel ke frontier jika valid dan belum ada."""
        if (1 <= r < rows - 1 and
                1 <= c < cols - 1 and
                (r, c) not in in_maze and
                (r, c) not in frontier_set):
            frontier.append((r, c))
            frontier_set.add((r, c))

    def get_maze_neighbors(r: int, c: int):
        """
        Kembalikan sel tetangga 2-langkah yang sudah in_maze.
        Tetangga 2-langkah = sel yang dipisahkan 1 tembok dari (r,c).
        """
        neighbors = []
        for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            nr, nc = r + dr, c + dc
            if (nr, nc) in in_maze:
                neighbors.append((nr, nc))
        return neighbors

    # Tambahkan tetangga 2-langkah dari sel awal ke frontier
    for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        add_frontier(start_r + dr, start_c + dc)

    # --- LANGKAH 4: Loop utama Prim ---
    while frontier:
        # 4a. Pilih frontier SECARA ACAK (inilah yang membuat maze "random")
        idx = random.randrange(len(frontier))
        fr, fc = frontier[idx]
        # Swap dengan elemen terakhir lalu pop → O(1) removal
        frontier[idx] = frontier[-1]
        frontier.pop()
        frontier_set.discard((fr, fc))

        # 4b. Cari tetangga yang sudah in_maze
        maze_neighbors = get_maze_neighbors(fr, fc)

        if not maze_neighbors:
            # Tidak ada tetangga in_maze → lewati (bisa terjadi karena
            # frontier_set tidak mencegah sel yang sudah in_maze ditambah)
            continue

        # 4c. Pilih satu tetangga in_maze secara acak
        nr, nc = random.choice(maze_neighbors)

        # Hancurkan tembok di antara (fr,fc) dan (nr,nc)
        wall_r = (fr + nr) // 2
        wall_c = (fc + nc) // 2
        grid[fr][fc]         = FLOOR
        grid[wall_r][wall_c] = FLOOR
        in_maze.add((fr, fc))

        # 4d. Tambahkan tetangga baru ke frontier
        for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            add_frontier(fr + dr, fc + dc)

    return grid


def print_maze(grid: List[List[int]]):
    """Tampilkan maze di terminal (untuk debugging)."""
    symbols = {WALL: '██', FLOOR: '  '}
    for row in grid:
        print(''.join(symbols[cell] for cell in row))


def get_floor_cells(grid: List[List[int]]) -> List[Tuple[int, int]]:
    """Kembalikan semua posisi yang merupakan FLOOR."""
    rows, cols = len(grid), len(grid[0])
    return [(r, c) for r in range(rows) for c in range(cols)
            if grid[r][c] == FLOOR]


# ── Demo standalone ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=== MAZE PRIM DEMO ===\n")
    maze = generate_maze(21, 21, seed=42)
    print_maze(maze)

    floors = get_floor_cells(maze)
    walls  = sum(row.count(WALL) for row in maze)
    print(f"\nTotal sel : {21*21}")
    print(f"Sel lantai: {len(floors)}")
    print(f"Sel tembok: {walls}")
