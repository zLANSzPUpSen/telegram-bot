from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import logger, TIMERS
from database import get_game, save_game, delete_game, Game
from messages import Messages
from game_logic import (
    safe_send_message, get_user_name, get_user_username,
    start_game_timer, start_game_immediately, process_footballers,
    next_fact_turn, process_mafia_guess, start_mafia_guess,
    process_player_voting
)


def get_active_games():
    """Функция для получения активных игр"""
    from database import active_games
    return active_games


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        args = context.args

        logger.info(f"🔹 /start от пользователя {user_id} в чате {chat_id}, аргументы: {args}")

        # Если команда в личном чате
        if update.effective_chat.type == "private":
            if args and args[0] == "join":
                await process_join_from_start(update, context, user_id)
            elif args and args[0] == "vote":
                await process_vote_from_start(update, context, user_id)
            elif args and args[0] == "footballer":
                await process_footballer_from_start(update, context, user_id)
            else:
                await update.message.reply_text(
                    Messages.confirm_join_game(),
                    reply_markup=Messages.confirm_join_button(),
                    parse_mode='Markdown'
                )
            return

        # Если команда в группе
        if update.effective_chat.type in ["group", "supergroup"]:
            await start_game_in_group(update, context)
            return
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")


async def process_join_from_start(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Обрабатывает присоединение через команду /start join"""
    try:
        player_name = await get_user_name(context.bot, user_id)
        logger.info(f"🔹 Обработка присоединения через /start join от {player_name} ({user_id})")

        # Ищем активную игру
        joined = False
        game_chat_id = None

        for chat_id, game in get_active_games().items():
            if user_id not in game.players:
                game.players.append(user_id)
                save_game(game)
                joined = True
                game_chat_id = chat_id
                logger.info(f"🔹 Пользователь {user_id} добавлен в игру в чате {chat_id}")
                break

        if joined and game_chat_id:
            await update.message.reply_text(
                f"🎉 **Вы успешно присоединились к игре!**\n\n"
                f"Возвращайтесь в группу чтобы следить за процессом.",
                parse_mode='Markdown'
            )

            # Сообщаем в группе
            await context.bot.send_message(
                chat_id=game_chat_id,
                text=Messages.player_joined(player_name, len(get_game(game_chat_id).players)),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ **Не удалось присоединиться к игре**\n\n"
                "Возможно:\n"
                "• Игра еще не начата\n"
                "• Вы уже в игре\n"
                "• Набор игроков завершен",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Ошибка в process_join_from_start: {e}")


async def process_vote_from_start(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Обрабатывает переход в личный чат для голосования"""
    try:
        # Ищем активную игру где пользователь является участником
        for chat_id, game in get_active_games().items():
            if user_id in game.players and game.phase == "discussion":
                await update.message.reply_text(
                    "🗳 **ВРЕМЯ ГОЛОСОВАНИЯ**\n\n"
                    "Выберите действие:",
                    reply_markup=Messages.discussion_buttons(),
                    parse_mode='Markdown'
                )
                return

        await update.message.reply_text(
            "❌ Сейчас нет активного голосования.\n\n"
            "Присоединяйтесь к игре в группе!",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка в process_vote_from_start: {e}")


async def process_footballer_from_start(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Обрабатывает переход в личный чат для выбора футболиста"""
    try:
        # Ищем активную игру где пользователь является участником
        for chat_id, game in get_active_games().items():
            if user_id in game.players and game.phase == "footballers":
                if user_id in game.footballers:
                    await update.message.reply_text(
                        f"✅ Вы уже выбрали футболиста: **{game.footballers[user_id]}**\n\n"
                        "Ожидаем пока все игроки выберут футболистов...",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "⚽ **ВЫБОР ФУТБОЛИСТА**\n\n"
                        "Введите имя любого известного футболиста:\n\n"
                        "⚠️ **ВНИМАНИЕ:** Пишите футболиста только в этот личный чат!",
                        parse_mode='Markdown'
                    )
                return

        await update.message.reply_text(
            "❌ Сейчас нет активного выбора футболистов.\n\n"
            "Присоединяйтесь к игре в группе!",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка в process_footballer_from_start: {e}")


async def start_game_in_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает игру в группе"""
    try:
        chat_id = update.effective_chat.id

        logger.info(f"🔹 УСТАНАВЛИВАЕМ ТАЙМЕР ДЛЯ ЧАТА {chat_id}")

        existing_game = get_game(chat_id)
        if existing_game:
            logger.info(f"🔹 Игра уже запущена в группе {chat_id}, игроков: {len(existing_game.players)}")
            try:
                bot_username = (await context.bot.get_me()).username
                await update.message.reply_text(
                    "🎮 Игра уже запущена! Присоединяйтесь!",
                    reply_markup=Messages.join_button(bot_username)
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение о существующей игре: {e}")
            return

        game = Game(chat_id)
        save_game(game)
        logger.info(f"🔹 Создана новая игра для группы {chat_id}")

        user_id = update.effective_user.id
        if user_id not in game.players:
            game.players.append(user_id)
            save_game(game)
            logger.info(f"🔹 Добавлен первый игрок {user_id}")

        try:
            bot_username = (await context.bot.get_me()).username
            await update.message.reply_text(
                Messages.game_started(len(game.players), bot_username),
                reply_markup=Messages.join_button(bot_username),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить стартовое сообщение: {e}")

        # Таймер на начало игры
        logger.info(f"⏰ Устанавливаем таймер на 30 секунд для чата {chat_id}")

        try:
            context.application.job_queue.run_once(
                start_game_timer,
                30,
                data={"chat_id": chat_id},
                name=f"game_start_{chat_id}"
            )
            logger.info("✅ ТАЙМЕР УСТАНОВЛЕН НА 30 СЕКУНД")
        except Exception as e:
            logger.error(f"Ошибка установки таймера: {e}")

    except Exception as e:
        logger.error(f"Ошибка в start_game_in_group: {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    try:
        query = update.callback_query
        user_id = update.effective_user.id
        data = query.data

        logger.info(f"🔹 Нажата кнопка {data} пользователем {user_id}")

        # Сразу отвечаем на нажатие чтобы избежать таймаута
        await query.answer()

        chat_id = query.message.chat.id
        logger.info(f"🔹 Chat ID: {chat_id}, User ID: {user_id}")

        # Проверяем есть ли активные игры
        active_games = get_active_games()
        logger.info(f"🔹 Активных игр: {len(active_games)}")

        if data == "confirm_join":
            logger.info("🔹 Обрабатываем confirm_join")
            await process_join_request(query, context, user_id)
        elif data == "finish_registration":
            logger.info("🔹 Обрабатываем finish_registration")
            await process_finish_registration(query, context, user_id, chat_id)
        elif data == "vote_mafia":
            logger.info("🔹 Обрабатываем vote_mafia")
            await process_vote_mafia(query, context, user_id, chat_id)
        elif data == "skip_vote":
            logger.info("🔹 Обрабатываем skip_vote")
            await process_skip_vote(query, context, user_id, chat_id)
        elif data.startswith("vote_player_"):
            logger.info("🔹 Обрабатываем vote_player")
            voted_player_id = int(data.split("_")[2])
            await process_vote_player(query, context, user_id, chat_id, voted_player_id)
        elif data == "mafia_reveal":
            logger.info("🔹 Обрабатываем mafia_reveal")
            await process_mafia_reveal(query, context, user_id, chat_id)
        elif data in ["correct_footballer", "wrong_footballer"]:
            logger.info("🔹 Обрабатываем footballer_vote")
            await process_footballer_vote(query, context, user_id, chat_id, data)
        else:
            logger.warning(f"🔹 Неизвестная кнопка: {data}")

    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}")
        try:
            await query.answer("❌ Произошла ошибка", show_alert=True)
        except:
            pass


async def process_finish_registration(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    """Обрабатывает завершение регистрации"""
    try:
        game = get_game(chat_id)
        if not game:
            await query.edit_message_text("❌ Игра не найдена!")
            return

        if len(game.players) < 3:
            await query.edit_message_text("❌ Недостаточно игроков для начала игры! (нужно минимум 3)")
            return

        # Отменяем таймер если он есть
        try:
            job_name = f"game_start_{chat_id}"
            current_jobs = context.application.job_queue.get_jobs_by_name(job_name)
            for job in current_jobs:
                job.schedule_removal()
        except Exception as e:
            logger.error(f"Ошибка отмены таймера: {e}")

        await query.edit_message_text("✅ Регистрация завершена! Начинаем игру...")
        await start_game_immediately(context, chat_id)

    except Exception as e:
        logger.error(f"Ошибка в process_finish_registration: {e}")


async def process_join_request(query, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Обрабатывает запрос на присоединение к игре"""
    try:
        player_name = await get_user_name(context.bot, user_id)
        logger.info(f"🔹 Обработка запроса на присоединение от {player_name} ({user_id})")

        # Ищем активную игру
        joined = False
        game_chat_id = None

        for chat_id, game in get_active_games().items():
            if user_id not in game.players:
                game.players.append(user_id)
                save_game(game)
                joined = True
                game_chat_id = chat_id
                logger.info(f"🔹 Пользователь {user_id} добавлен в игру в чате {chat_id}")
                break

        if joined and game_chat_id:
            # Сообщаем в личном чате
            await query.edit_message_text(
                f"🎉 **Вы успешно присоединились к игре!**\n\n"
                f"Возвращайтесь в группу чтобы следить за процессом.",
                parse_mode='Markdown'
            )

            # Сообщаем в группе
            await context.bot.send_message(
                chat_id=game_chat_id,
                text=Messages.player_joined(player_name, len(get_game(game_chat_id).players)),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ **Не удалось присоединиться к игре**\n\n"
                "Возможно:\n"
                "• Игра еще не начата\n"
                "• Вы уже в игре\n"
                "• Набор игроков завершен",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Ошибка в process_join_request: {e}")


async def process_vote_mafia(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    """Обрабатывает голос за начало голосования за мафию"""
    try:
        logger.info(f"🔹 process_vote_mafia: user_id={user_id}, chat_id={chat_id}")

        game = get_game(chat_id)
        if not game:
            logger.warning(f"🔹 Игра не найдена для chat_id: {chat_id}")
            await query.answer("❌ Игра не найдена", show_alert=True)
            return

        if game.phase != "discussion":
            logger.warning(f"🔹 Неправильная фаза: {game.phase}, должна быть discussion")
            await query.answer("❌ Сейчас не время для голосования", show_alert=True)
            return

        if user_id not in game.votes and user_id in game.players:
            game.votes[user_id] = user_id
            save_game(game)

            logger.info(f"🔹 Голос за мафию принят. Всего голосов: {len(game.votes)}")

            # Подтверждение в личном чате
            await query.edit_message_text(
                "✅ Вы проголосовали за **начало голосования за мафию**\n\n"
                "Ожидаем решения других игроков...",
                parse_mode='Markdown'
            )

            # Уведомление в группе
            player_name = await get_user_username(context.bot, user_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎯 {player_name} проголосовал за **голосование за мафию**",
                parse_mode='Markdown'
            )
        else:
            logger.warning(f"🔹 Пользователь {user_id} уже голосовал или не в игре")
            await query.answer("❌ Вы уже голосовали или не участвуете в игре", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в process_vote_mafia: {e}")
        try:
            await query.answer("❌ Ошибка при голосовании", show_alert=True)
        except:
            pass


async def process_skip_vote(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    """Обрабатывает голос за пропуск"""
    try:
        logger.info(f"🔹 process_skip_vote: user_id={user_id}, chat_id={chat_id}")

        game = get_game(chat_id)
        if not game:
            logger.warning(f"🔹 Игра не найдена для chat_id: {chat_id}")
            await query.answer("❌ Игра не найдена", show_alert=True)
            return

        if game.phase != "discussion":
            logger.warning(f"🔹 Неправильная фаза: {game.phase}, должна быть discussion")
            await query.answer("❌ Сейчас не время для голосования", show_alert=True)
            return

        if user_id in game.players:
            game.skip_votes += 1
            save_game(game)

            logger.info(f"🔹 Голос за пропуск принят. Всего пропусков: {game.skip_votes}")

            # Подтверждение в личном чате
            await query.edit_message_text(
                "✅ Вы проголосовали за **пропуск**\n\n"
                "Ожидаем решения других игроков...",
                parse_mode='Markdown'
            )

            # Уведомление в группе
            player_name = await get_user_username(context.bot, user_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎯 {player_name} проголосовал за **пропуск**",
                parse_mode='Markdown'
            )
        else:
            logger.warning(f"🔹 Пользователь {user_id} не в игре")
            await query.answer("❌ Вы не участвуете в игре", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в process_skip_vote: {e}")
        try:
            await query.answer("❌ Ошибка при голосовании", show_alert=True)
        except:
            pass


async def process_vote_player(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int,
                              voted_player_id: int):
    """Обрабатывает голос за конкретного игрока"""
    try:
        game = get_game(chat_id)
        if not game or game.phase != "voting":
            return

        if user_id in game.players:
            game.votes[user_id] = voted_player_id
            save_game(game)

            total_players = len(game.players)
            current_votes = len(game.votes)

            await query.edit_message_text(
                f"✅ Вы проголосовали за игрока\n"
                f"🗳 Проголосовало: {current_votes}/{total_players}",
                parse_mode='Markdown'
            )

            if current_votes == total_players:
                await process_player_voting(context, chat_id)
    except Exception as e:
        logger.error(f"Ошибка в process_vote_player: {e}")


async def process_mafia_reveal(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    """Обрабатывает вскрытие мафии"""
    try:
        logger.info(f"🔹 process_mafia_reveal: user_id={user_id}, chat_id={chat_id}")

        game = get_game(chat_id)
        if not game:
            logger.warning(f"🔹 Игра не найдена для chat_id: {chat_id}")
            await query.answer("❌ Игра не найдена", show_alert=True)
            return

        if user_id != game.mafia:
            await query.answer("❌ Вы не мафия!", show_alert=True)
            return

        # Подтверждаем нажатие кнопки
        await query.answer()

        game.mafia_revealed = True
        save_game(game)

        # Быстрое редактирование сообщения
        try:
            await query.edit_message_text(
                "🎭 Вы вскрылись как мафия! Ожидайте угадывания футболиста...",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Не удалось отредактировать сообщение: {e}")

        # Уведомляем группу (с обработкой таймаута)
        try:
            player_name = await get_user_username(context.bot, user_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎭 **МАФИЯ ВСКРЫЛАСЬ!**\n\n"
                     f"Игрок {player_name} признался что он мафия!\n"
                     f"Теперь он пытается угадать футболиста...",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление в группу: {e}")

        # Начинаем угадывание
        await start_mafia_guess(context, chat_id)

    except Exception as e:
        logger.error(f"Ошибка в process_mafia_reveal: {e}")
        try:
            await query.answer("❌ Ошибка при вскрытии", show_alert=True)
        except:
            pass


async def process_footballer_vote(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, vote: str):
    """Обрабатывает голосование за правильность футболиста"""
    try:
        game = get_game(chat_id)
        if not game:
            return

        if vote == "correct_footballer":
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ **Игроки подтвердили что футболист правильный!**\n\n"
                     "🎭 **Мафия побеждает!**"
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ **Игроки сказали что футболист неправильный!**\n\n"
                     "🏆 **Мирные игроки побеждают!**"
            )
        delete_game(chat_id)
    except Exception as e:
        logger.error(f"Ошибка в process_footballer_vote: {e}")


async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщения в личном чате"""
    try:
        user_id = update.effective_user.id
        message_text = update.message.text.strip()

        logger.info(f"🔹 Личное сообщение от {user_id}: {message_text}")

        # Проверяем, находится ли пользователь в фазе выбора футболиста
        for chat_id, game in get_active_games().items():
            if user_id in game.players and game.phase == "footballers" and user_id not in game.footballers:
                # Сохраняем футболиста
                game.footballers[user_id] = message_text
                save_game(game)

                await update.message.reply_text(
                    f"✅ **Вы выбрали футболиста:** {message_text}\n\n"
                    f"Ожидаем пока все игроки выберут футболистов...",
                    parse_mode='Markdown'
                )
                logger.info(f"🔹 Пользователь {user_id} выбрал футболиста: {message_text}")

                # Проверяем, все ли выбрали футболистов
                if len(game.footballers) == len(game.players):
                    logger.info(f"🔹 Все игроки выбрали футболистов, начинаем игру в чате {chat_id}")
                    await process_footballers(context, chat_id)
                else:
                    remaining = len(game.players) - len(game.footballers)
                    logger.info(f"🔹 Ожидаем футболистов: {remaining} осталось")

                return

        # Если сообщение не обработано как футболист, отправляем подсказку
        await update.message.reply_text(
            "ℹ️ Если вы участвуете в игре, дождитесь когда бот попросит вас ввести футболиста.\n\n"
            "Для присоединения к игре используйте команду /start в группе где проходит игра."
        )

    except Exception as e:
        logger.error(f"Ошибка в handle_private_message: {e}")


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщения в групповом чате"""
    try:
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        chat_id = update.effective_chat.id

        logger.info(f"🔹 Групповое сообщение от {user_id} в {chat_id}: {message_text}")

        # Проверяем, находится ли игра в фазе фактов и является ли пользователь текущим игроком
        game = get_game(chat_id)
        if game and game.phase == "facts":
            if (game.current_player_index < len(game.fact_order) and
                    game.fact_order[game.current_player_index] == user_id):

                # Сохраняем факт вместе с ID игрока
                current_player = game.fact_order[game.current_player_index]
                game.facts.append({
                    'player_id': current_player,
                    'text': message_text
                })
                game.current_player_index += 1
                save_game(game)

                try:
                    await update.message.reply_text("✅ Факт принят!")
                except Exception as e:
                    logger.warning(f"Не удалось отправить подтверждение: {e}")

                logger.info(
                    f"🔹 Факт сохранен, переходим к следующему игроку. Текущий индекс: {game.current_player_index}")

                await next_fact_turn(context, chat_id)
                return

        # Проверяем, является ли сообщение попыткой угадать футболиста мафией
        if game and game.phase == "mafia_guess" and user_id == game.mafia:
            await process_mafia_guess(context, chat_id, message_text)
            return

    except Exception as e:
        logger.error(f"Ошибка в handle_group_message: {e}")
        # Не прерываем работу бота при ошибках


def setup_handlers(application):
    """Настройка обработчиков"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message
    ))

    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_group_message
    ))