import aiosqlite
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "ghatalan_rank.db"

def get_week_key(dt=None):
    dt = dt or datetime.now(ZoneInfo("Asia/Tehran"))
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY, name TEXT NOT NULL, username TEXT,
            created_at TEXT NOT NULL)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT NOT NULL,
            deck TEXT NOT NULL, points INTEGER NOT NULL, admin_id INTEGER NOT NULL,
            week_key TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(player_id) REFERENCES players(player_id))""")
        await db.commit()

async def add_player(name, username):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT COUNT(*) FROM players")
        n = (await cur.fetchone())[0] + 1
        pid = f"KR-{n:06d}"
        while True:
            cur = await db.execute("SELECT 1 FROM players WHERE player_id=?", (pid,))
            if not await cur.fetchone(): break
            n += 1
            pid = f"KR-{n:06d}"
        await db.execute("INSERT INTO players VALUES(?,?,?,?)",
                         (pid, name, username, datetime.now().astimezone().isoformat(timespec="seconds")))
        await db.commit()
        return pid

async def list_players():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM players ORDER BY name COLLATE NOCASE")
        return [dict(r) for r in await cur.fetchall()]

async def find_players(query):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        q = query.lstrip("@")
        cur = await db.execute("""SELECT * FROM players WHERE player_id=? OR username=? OR name LIKE ? ORDER BY name LIMIT 10""",
                               (query, q, f"%{query}%"))
        return [dict(r) for r in await cur.fetchall()]

async def get_player(player_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM players WHERE player_id=?", (player_id,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def add_score(player_id, deck, points, admin_id, week_key):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO scores(player_id,deck,points,admin_id,week_key,created_at) VALUES(?,?,?,?,?,?)",
                         (player_id, deck, points, admin_id, week_key, datetime.now().astimezone().isoformat(timespec="seconds")))
        await db.commit()

async def weekly_board(week_key):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""SELECT p.player_id,p.name,SUM(s.points) points,COUNT(*) games
          FROM scores s JOIN players p ON p.player_id=s.player_id WHERE s.week_key=?
          GROUP BY p.player_id ORDER BY points DESC,games ASC,p.name ASC""", (week_key,))
        return [dict(r) for r in await cur.fetchall()]

async def all_time_board():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""SELECT p.player_id,p.name,COALESCE(SUM(s.points),0) points,COUNT(s.id) games
          FROM players p LEFT JOIN scores s ON p.player_id=s.player_id
          GROUP BY p.player_id ORDER BY points DESC,games ASC,p.name ASC""")
        return [dict(r) for r in await cur.fetchall()]

async def player_history(player_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM scores WHERE player_id=? ORDER BY id DESC LIMIT 30", (player_id,))
        return [dict(r) for r in await cur.fetchall()]

async def get_decks():
    return []
