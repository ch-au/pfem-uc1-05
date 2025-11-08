#!/usr/bin/env python3
"""
Generate quick sanity statistics for the FSV Mainz 05 archive database.

Usage:
    python summarize_archive.py [--db fsv_archive_complete.db] [--plot output.png]
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Tuple

try:
    import matplotlib.pyplot as plt  # type: ignore
except ImportError:  # pragma: no cover - matplotlib optional
    plt = None


def query_all(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> list[Tuple]:
    cur = conn.execute(sql, params)
    return cur.fetchall()


def print_header(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def main(db_path: Path, plot_path: Optional[Path]) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print_header("Summary")
    total_matches = query_all(conn, "SELECT COUNT(*) FROM matches")[0][0]
    total_players = query_all(conn, "SELECT COUNT(*) FROM players")[0][0]
    total_goals = query_all(conn, "SELECT COUNT(*) FROM goals")[0][0]
    print(f"Matches      : {total_matches:,}")
    print(f"Players      : {total_players:,}")
    print(f"Goals        : {total_goals:,}")

    print_header("Seasons with Matches")
    seasons = query_all(
        conn,
        """
        SELECT s.label, COUNT(m.match_id) AS games
        FROM seasons s
        LEFT JOIN season_competitions sc ON sc.season_id = s.season_id
        LEFT JOIN matches m ON m.season_competition_id = sc.season_competition_id
        GROUP BY s.label
        ORDER BY s.label
        """,
    )
    if seasons:
        zero = [label for label, games in seasons if games == 0]
        print(f"Total seasons: {len(seasons)}")
        print(f"Seasons with matches: {len(seasons) - len(zero)}")
        if zero:
            print("No data seasons:", ", ".join(zero))

    print_header("Top Players by Appearances")
    top_players = query_all(
        conn,
        """
        SELECT p.name, COUNT(*) AS apps
        FROM match_lineups ml
        JOIN players p ON p.player_id = ml.player_id
        GROUP BY p.player_id
        ORDER BY apps DESC
        LIMIT 10
        """,
    )
    for name, apps in top_players:
        print(f"{apps:4d}  {name}")

    print_header("Top Scorers")
    top_scorers = query_all(
        conn,
        """
        SELECT p.name, COUNT(*) AS goals
        FROM goals g
        JOIN players p ON p.player_id = g.player_id
        GROUP BY p.player_id
        ORDER BY goals DESC
        LIMIT 10
        """,
    )
    for name, goals in top_scorers:
        print(f"{goals:4d}  {name}")

    print_header("Matches per Season (first 20)")
    for label, games in seasons[:20]:
        print(f"{label:8s}  {games:4d}")

    if plot_path:
        if plt is None:
            raise RuntimeError("matplotlib is required for plotting. Install it or omit --plot.")
        labels = [label for label, _ in seasons]
        counts = [games for _, games in seasons]
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(labels, counts, marker="o", linestyle="-", linewidth=1)
        ax.set_title("Matches per Season")
        ax.set_xlabel("Season")
        ax.set_ylabel("Matches")
        ax.tick_params(axis='x', which='both', labelrotation=90, labelsize=7)
        fig.tight_layout()
        fig.savefig(plot_path)
        print_header("Plot")
        print(f"Saved plot to {plot_path}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarise the FSV archive database.")
    parser.add_argument(
        "--db",
        default="fsv_archive_complete.db",
        type=Path,
        help="Path to the SQLite database (default: fsv_archive_complete.db)",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        help="Optional output path for a matches-per-season plot (requires matplotlib).",
    )
    args = parser.parse_args()

    main(args.db, args.plot)
