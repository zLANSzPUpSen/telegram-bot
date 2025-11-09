from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List


class Messages:
    @staticmethod
    def game_started(players_count: int, bot_username: str) -> str:
        return (
            f"⚽🎭 **ФУТБОЛЬНАЯ МАФИЯ** 🎭⚽\n\n"
            f"👥 Игроков присоединилось: {players_count}\n"
            f"⏱ Набор игроков продлится 30 секунд...\n\n"
            f"🎯 **Как присоединиться:**\n"
            f"1. Нажмите кнопку '🎮 Присоединиться к игре' ниже\n"
            f"2. Бот откроет личный чат с вами\n"
            f"3. Нажмите '✅ Войти в игру' в личном чате"
        )

    @staticmethod
    def join_button(bot_username: str) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("🎮 Присоединиться к игре", url=f"https://t.me/{bot_username}?start=join")],
            [InlineKeyboardButton("✅ Завершить регистрацию", callback_data="finish_registration")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def confirm_join_game() -> str:
        return (
            "🎮 **ПРИСОЕДИНЕНИЕ К ИГРЕ**\n\n"
            "Вы хотите присоединиться к Футбольной Мафии!\n"
            "Нажмите кнопку ниже чтобы войти в игру:"
        )

    @staticmethod
    def confirm_join_button() -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("✅ Войти в игру", callback_data="confirm_join")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def player_joined(player_name: str, total_players: int) -> str:
        return (
            f"✅ **{player_name}** присоединился к игре!\n"
            f"👥 Всего игроков: **{total_players}**"
        )

    @staticmethod
    def you_are_mafia() -> str:
        return (
            "🎭 **ВЫ МАФИЯ!** 🎭\n\n"
            "Ваша задача:\n"
            "• Слушайте факты о футболисте\n"
            "• Попробуйте угадать его\n"
            "• Или вскройтесь когда будете готовы\n\n"
            "⚠️ Не выдавайте себя!"
        )

    @staticmethod
    def you_are_peaceful(footballer: str) -> str:
        return (
            "⚽ **ВЫ МИРНЫЙ ИГРОК** ⚽\n\n"
            f"Загаданный футболист: **{footballer}**\n\n"
            "Ваша задача:\n"
            "• Говорите правдивые факты\n"
            "• Не называйте футболиста прямо\n"
            "• Вычислите мафию!"
        )

    @staticmethod
    def fact_turn(player_name: str) -> str:
        return f"📢 **Факт называет {player_name}**\n\n💬 Напишите факт о футболисте в этот чат:"

    @staticmethod
    def discussion_phase() -> str:
        return (
            "💬 **ФАЗА ОБСУЖДЕНИЯ**\n\n"
            "У вас 2 минуты на обсуждение!\n"
            "Выберите действие:"
        )

    @staticmethod
    def discussion_buttons() -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("🗳 Голосовать за мафию", callback_data="vote_mafia")],
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_vote")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def vote_buttons(players: List[int], current_player: int) -> InlineKeyboardMarkup:
        keyboard = []
        row = []
        for i, player_id in enumerate(players):
            if player_id != current_player:
                row.append(InlineKeyboardButton(f"👤 Игрок {i + 1}", callback_data=f"vote_player_{player_id}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
        if row:
            keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def mafia_reveal_button() -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("🎭 ВСКРЫТЬСЯ КАК МАФИЯ", callback_data="mafia_reveal")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def confirm_footballer_buttons() -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("✅ Правильная", callback_data="correct_footballer")],
            [InlineKeyboardButton("❌ Неправильная", callback_data="wrong_footballer")]
        ]
        return InlineKeyboardMarkup(keyboard)