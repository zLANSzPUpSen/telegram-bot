import sqlite3
import json
from datetime import datetime
from typing import Dict, List
from config import logger


class GameDatabase:
    def __init__(self, db_path="mafia_games.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                chat_id INTEGER PRIMARY KEY,
                game_data TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def save_game(self, chat_id: int, game_data: dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO games (chat_id, game_data, created_at, updated_at)
            VALUES (?, ?, COALESCE((SELECT created_at FROM games WHERE chat_id=?), ?), ?)
        ''', (chat_id, json.dumps(game_data), chat_id, now, now))
        conn.commit()
        conn.close()

    def load_game(self, chat_id: int) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT game_data FROM games WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        conn.close()
        return json.loads(result[0]) if result else None

    def delete_game(self, chat_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM games WHERE chat_id = ?', (chat_id,))
        conn.commit()
        conn.close()


class Game:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.players: List[int] = []
        self.footballers: Dict[int, str] = {}
        self.mafia: int = None
        self.chosen_footballer: str = None
        self.facts: List[str] = []
        self.fact_order: List[int] = []
        self.current_player_index: int = 0
        self.votes: Dict[int, int] = {}
        self.skip_votes: int = 0
        self.phase: str = "waiting"
        self.mafia_revealed: bool = False
        self.mafia_guess: str = None
        self.db = GameDatabase()

    def save(self):
        game_data = {
            'players': self.players,
            'footballers': self.footballers,
            'mafia': self.mafia,
            'chosen_footballer': self.chosen_footballer,
            'facts': self.facts,
            'fact_order': self.fact_order,
            'current_player_index': self.current_player_index,
            'votes': self.votes,
            'skip_votes': self.skip_votes,
            'phase': self.phase,
            'mafia_revealed': self.mafia_revealed,
            'mafia_guess': self.mafia_guess
        }
        self.db.save_game(self.chat_id, game_data)

    @classmethod
    def load(cls, chat_id: int):
        db = GameDatabase()
        game_data = db.load_game(chat_id)
        if game_data:
            game = cls(chat_id)
            game.players = game_data['players']
            game.footballers = game_data['footballers']
            game.mafia = game_data['mafia']
            game.chosen_footballer = game_data['chosen_footballer']
            game.facts = game_data['facts']
            game.fact_order = game_data.get('fact_order', [])
            game.current_player_index = game_data.get('current_player_index', 0)
            game.votes = game_data.get('votes', {})
            game.skip_votes = game_data.get('skip_votes', 0)
            game.phase = game_data.get('phase', 'waiting')
            game.mafia_revealed = game_data.get('mafia_revealed', False)
            game.mafia_guess = game_data.get('mafia_guess')
            return game
        return None


# Глобальное хранилище активных игр
active_games: Dict[int, Game] = {}


def get_game(chat_id: int) -> Game:
    if chat_id in active_games:
        return active_games[chat_id]
    game = Game.load(chat_id)
    if game:
        active_games[chat_id] = game
        return game
    return None


def save_game(game: Game):
    game.save()
    active_games[game.chat_id] = game


def delete_game(chat_id: int):
    if chat_id in active_games:
        del active_games[chat_id]
    db = GameDatabase()
    db.delete_game(chat_id)