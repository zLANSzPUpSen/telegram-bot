import random
import asyncio
from typing import Dict, List
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import logger, TIMERS
from database import get_game, save_game, delete_game
from messages import Messages


async def safe_send_message(bot, chat_id: int, text: str, **kwargs):
    try:
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки {chat_id}: {e}")
        return False


async def get_user_name(bot, user_id: int) -> str:
    try:
        user = await bot.get_chat(user_id)
        return user.first_name or f"Игрок {user_id}"
    except Exception as e:
        logger.error(f"Ошибка получения имени пользователя {user_id}: {e}")
        return f"Игрок {user_id}"


async def get_user_username(bot, user_id: int) -> str:
    try:
        user = await bot.get_chat(user_id)
        return f"@{user.username}" if user.username else user.first_name
    except Exception as e:
        logger.error(f"Ошибка получения username пользователя {user_id}: {e}")
        return f"Игрок {user_id}"


# Таймеры
async def start_game_timer(context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("🎯 ТАЙМЕР СРАБОТАЛ!")
        chat_id = context.job.data["chat_id"]
        game = get_game(chat_id)

        if not game:
            logger.error(f"❌ ИГРА НЕ НАЙДЕНА ДЛЯ ЧАТА {chat_id}")
            return

        if len(game.players) < 3:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Недостаточно игроков для начала игры! (нужно минимум 3)"
            )
            delete_game(chat_id)
            return

        await start_game_immediately(context, chat_id)
    except Exception as e:
        logger.error(f"Ошибка в start_game_timer: {e}")


async def start_game_immediately(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = get_game(chat_id)
    if not game:
        return

    logger.info("🎮 НАЧИНАЕМ ИГРУ! Выбираем мафию...")
    game.mafia = random.choice(game.players)
    game.phase = "footballers"
    save_game(game)

    bot_username = (await context.bot.get_me()).username

    # Сообщение в группе с кнопкой перехода в личный чат
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ **Набор игроков завершен!**\n\n"
             "⚽ **Время выбрать футболистов!**\n\n"
             "📱 **Перейдите в личный чат с ботом чтобы выбрать футболиста:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Выбрать футболиста", url=f"https://t.me/{bot_username}?start=footballer")]
        ]),
        parse_mode='Markdown'
    )

    # Отправляем запросы в личные сообщения
    successful_sends = 0
    for player_id in game.players:
        try:
            success = await safe_send_message(
                context.bot,
                player_id,
                "⚽ **ВЫБОР ФУТБОЛИСТА**\n\n"
                "Введите имя любого известного футболиста:\n\n"
                "⚠️ **ВНИМАНИЕ:** Пишите футболиста только в этот личный чат!",
                parse_mode='Markdown'
            )
            if success:
                successful_sends += 1
        except Exception as e:
            logger.error(f"Ошибка отправки игроку {player_id}: {e}")

    logger.info(f"📨 Отправлено личных сообщений: {successful_sends}/{len(game.players)}")


async def discussion_timer(context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = context.job.data["chat_id"]
        game = get_game(chat_id)

        if not game or game.phase != "discussion":
            return

        await check_voting_results(context, chat_id)
    except Exception as e:
        logger.error(f"Ошибка в discussion_timer: {e}")


async def mafia_guess_timer(context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = context.job.data["chat_id"]
        game = get_game(chat_id)

        if not game or game.phase != "mafia_guess":
            return

        await context.bot.send_message(
            chat_id=chat_id,
            text="⏰ Время вышло! Мафия не успела угадать футболиста.\n\n"
                 "🏆 **Мирные игроки побеждают!**"
        )
        delete_game(chat_id)
    except Exception as e:
        logger.error(f"Ошибка в mafia_guess_timer: {e}")


# Фазы игры
async def start_facts_phase(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Начинает фазу фактов"""
    game = get_game(chat_id)
    if not game:
        return

    # Создаем случайный порядок только если его еще нет
    if not game.fact_order:
        game.fact_order = game.players.copy()
        random.shuffle(game.fact_order)
        logger.info(f"🔹 Установлен случайный порядок: {game.fact_order}")

    game.phase = "facts"
    game.current_player_index = 0
    game.facts = []
    save_game(game)

    # Создаем текст с порядком игроков
    order_text = "📋 **Порядок игроков:**\n"
    for i, player_id in enumerate(game.fact_order, 1):
        player_name = await get_user_username(context.bot, player_id)
        order_text += f"{i}. {player_name}\n"

    await context.bot.send_message(
        chat_id=chat_id,
        text="💬 **ФАЗА ФАКТОВ**\n\n" +
             order_text +
             "\n📢 **Пишите факты прямо в этот групповой чат!**",
        parse_mode='Markdown'
    )

    await next_fact_turn(context, chat_id)


async def next_fact_turn(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = get_game(chat_id)
    if not game or game.phase != "facts":
        return

    if game.current_player_index >= len(game.fact_order):
        await start_discussion_phase(context, chat_id)
        return

    current_player = game.fact_order[game.current_player_index]
    player_name = await get_user_username(context.bot, current_player)

    await context.bot.send_message(
        chat_id=chat_id,
        text=Messages.fact_turn(player_name),
        parse_mode='Markdown'
    )

    if current_player == game.mafia:
        await safe_send_message(
            context.bot,
            current_player,
            "💬 Ваша очередь говорить факт. Вы можете вскрыться как мафия:",
            reply_markup=Messages.mafia_reveal_button()
        )


async def start_discussion_phase(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Начинает фазу обсуждения"""
    game = get_game(chat_id)
    if not game:
        return

    game.phase = "discussion"
    game.votes = {}
    game.skip_votes = 0
    save_game(game)

    # Показываем все сказанные факты в группе с указанием игроков
    facts_text = "📋 **Все сказанные факты:**\n\n"
    for i, fact_data in enumerate(game.facts, 1):
        player_name = await get_user_username(context.bot, fact_data['player_id'])
        facts_text += f"{i}. **{player_name}:** {fact_data['text']}\n"

    await context.bot.send_message(
        chat_id=chat_id,
        text=facts_text,
        parse_mode='Markdown'
    )

    bot_username = (await context.bot.get_me()).username

    # Сообщение в группе с кнопкой перехода в личный чат
    await context.bot.send_message(
        chat_id=chat_id,
        text="💬 **ФАЗА ОБСУЖДЕНИЯ**\n\n"
             "У вас 2 минуты на обсуждение!\n\n"
             "📱 **Для голосования перейдите в личный чат с ботом:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Перейти в личный чат", url=f"https://t.me/{bot_username}?start=vote")]
        ]),
        parse_mode='Markdown'
    )

    # Отправляем кнопки голосования в личные сообщения каждому игроку
    for player_id in game.players:
        await safe_send_message(
            context.bot,
            player_id,
            "🗳 **ВРЕМЯ ГОЛОСОВАНИЯ**\n\n"
            "Выберите действие:\n"
            "• 🗳 **Голосовать за мафию** - начать голосование за игроков\n"
            "• ⏭ **Пропустить** - продолжить игру без голосования",
            reply_markup=Messages.discussion_buttons()
        )

    # Устанавливаем таймер на 2 минуты
    try:
        context.application.job_queue.run_once(
            discussion_timer,
            TIMERS['discussion'],
            data={"chat_id": chat_id},
            name=f"discussion_{chat_id}"
        )
    except Exception as e:
        logger.error(f"Ошибка установки таймера обсуждения: {e}")


async def check_voting_results(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = get_game(chat_id)
    if not game:
        return

    total_players = len(game.players)
    vote_mafia_count = len(game.votes)
    skip_count = game.skip_votes

    if vote_mafia_count > skip_count and vote_mafia_count > total_players // 2:
        await start_player_voting(context, chat_id)
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 **Начинается новый раунд!**\n\n"
                 "Игроки продолжают говорить факты..."
        )
        await start_facts_phase(context, chat_id)


async def start_player_voting(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = get_game(chat_id)
    if not game:
        return

    game.phase = "voting"
    game.votes = {}
    save_game(game)

    for player_id in game.players:
        await safe_send_message(
            context.bot,
            player_id,
            "🗳 **ГОЛОСОВАНИЕ ЗА МАФИЮ**\n\n"
            "Выберите игрока, которого считаете мафией:",
            reply_markup=Messages.vote_buttons(game.players, player_id)
        )

    await context.bot.send_message(
        chat_id=chat_id,
        text="🗳 **Началось голосование за мафию!**\n\n"
             "Все игроки получили личные сообщения для голосования."
    )


async def process_player_voting(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = get_game(chat_id)
    if not game:
        return

    # Подсчитываем голоса
    vote_count = {}
    for voted_player in game.votes.values():
        vote_count[voted_player] = vote_count.get(voted_player, 0) + 1

    if not vote_count:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Никто не проголосовал. Начинается новый раунд."
        )
        await start_facts_phase(context, chat_id)
        return

    # Находим игрока с наибольшим количеством голосов
    max_votes = max(vote_count.values())
    suspected_players = [player for player, votes in vote_count.items() if votes == max_votes]

    if len(suspected_players) > 1:
        # Ничья
        await context.bot.send_message(
            chat_id=chat_id,
            text="🤝 **Ничья в голосовании!** Начинается новый раунд."
        )
        await start_facts_phase(context, chat_id)
        return

    suspected_player = suspected_players[0]

    if suspected_player == game.mafia:
        # Угадали мафию
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎯 **Игрок {await get_user_username(context.bot, suspected_player)} был мафией!**\n\n"
                 "Теперь мафия пытается угадать футболиста за 30 секунд..."
        )
        await start_mafia_guess(context, chat_id)
    else:
        # Ошиблись
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **Игрок {await get_user_username(context.bot, suspected_player)} не был мафией!**\n\n"
                 "🎭 **Мафия побеждает!**"
        )
        delete_game(chat_id)


async def start_mafia_guess(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Мафия пытается угадать футболиста"""
    game = get_game(chat_id)
    if not game:
        return

    game.phase = "mafia_guess"
    save_game(game)

    await safe_send_message(
        context.bot,
        game.mafia,
        "🎭 **УГАДАЙТЕ ФУТБОЛИСТА!**\n\n"
        "У вас 30 секунд чтобы написать фамилию футболиста:"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text="⏰ **Мафия угадывает футболиста...**\n"
             "У них 30 секунд!"
    )

    # Таймер на 30 секунд
    try:
        context.application.job_queue.run_once(
            mafia_guess_timer,
            TIMERS['mafia_guess'],
            data={"chat_id": chat_id},
            name=f"mafia_guess_{chat_id}"
        )
    except Exception as e:
        logger.error(f"Ошибка установки таймера мафии: {e}")


async def process_mafia_guess(context: ContextTypes.DEFAULT_TYPE, chat_id: int, guess: str):
    """Обрабатывает попытку мафии угадать футболиста"""
    game = get_game(chat_id)
    if not game:
        return

    game.mafia_guess = guess
    save_game(game)

    # Проверяем точное совпадение
    if guess.lower().strip() == game.chosen_footballer.lower().strip():
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎯 **Мафия угадала!** Футболист: {game.chosen_footballer}\n\n"
                 "🎭 **Мафия побеждает!**"
        )
        delete_game(chat_id)
    else:
        # Если нет точного совпадения, голосуем
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🤔 **Мафия предложила:** {guess}\n\n"
                 f"**Правильный ли это футболист?**\n"
                 f"Настоящий футболист: {game.chosen_footballer}",
            reply_markup=Messages.confirm_footballer_buttons()
        )


async def process_footballers(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        game = get_game(chat_id)
        if not game:
            logger.error(f"❌ Игра не найдена при обработке футболистов для чата {chat_id}")
            return

        logger.info(f"🔹 Обрабатываем футболистов для игры в чате {chat_id}")

        # Выбираем футболиста от мирного игрока
        peaceful_players = [p for p in game.players if p != game.mafia]
        if peaceful_players:
            chosen_player = random.choice(peaceful_players)
            game.chosen_footballer = game.footballers[chosen_player]
            logger.info(f"🔹 Выбран футболист: {game.chosen_footballer} от игрока {chosen_player}")

        save_game(game)

        # Уведомляем мафию
        if game.mafia:
            await safe_send_message(
                context.bot,
                game.mafia,
                Messages.you_are_mafia(),
                parse_mode='Markdown'
            )
            logger.info(f"🔹 Уведомлена мафия: {game.mafia}")

        # Уведомляем мирных игроков
        peaceful_count = 0
        for player_id in game.players:
            if player_id != game.mafia and game.chosen_footballer:
                await safe_send_message(
                    context.bot,
                    player_id,
                    Messages.you_are_peaceful(game.chosen_footballer),
                    parse_mode='Markdown'
                )
                peaceful_count += 1

        logger.info(f"🔹 Уведомлено мирных игроков: {peaceful_count}")

        await context.bot.send_message(
            chat_id=chat_id,
            text="🎮 **Игра началась!**\n\n"
                 "Мирные игроки знают загаданного футболиста.\n"
                 "Мафия пытается угадать его по фактам.\n\n"
                 "💬 **Начинается фаза фактов!**",
            parse_mode='Markdown'
        )

        # Начинаем фазу фактов
        await start_facts_phase(context, chat_id)
    except Exception as e:
        logger.error(f"Ошибка в process_footballers: {e}")