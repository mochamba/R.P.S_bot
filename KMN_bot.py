from aiogram import Bot, Dispatcher, executor, types
from os import getenv
from sys import exit
from aiogram.dispatcher.filters import Text
from botback.BotClasses import DataBase, Game
import re
import asyncio

bot_token = getenv('BOT_TOKEN')
if not bot_token:
    exit("Error - not BOT_TOKEN in Venv")

bot = Bot(token=bot_token)
dp = Dispatcher(bot)

#  Присвоение к переменной экземпляра класса для работы с базой пользователей
db = DataBase()
# Переменная для работы с диспетчером дуэлей и турниров
game = Game()


@dp.message_handler(commands=["start"])
async def init(message: types.message):
    """Обработчик Команды «/start»"""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True, selective=True)
    buttons = ["Дуэль!", "Турнир!", 'Отмена!']
    keyboard.add(*buttons)
    name = message.from_user.username
    await message.answer(f"@{name} Выберите тип соревнования", reply_markup=keyboard)


@dp.message_handler(commands=["registrate"])
async def reg_in_db(message: types.message):
    """Обработчик Команды «/registrate»"""
    user = await db.get_user(message)
    name = message.from_user.username
    keyboard = types.ReplyKeyboardRemove()
    if user['total_duels'] == 0 and user['win_in_duels'] == 0 and user['win_in_tounaments'] == 0:
        await message.answer(f"@{name} Зарегистрирован в базе данных", reply_markup=keyboard)
    else:
        await message.answer(f"@{name} Уже был зарегестрирован", reply_markup=keyboard)


@dp.message_handler(Text(equals="Дуэль!"))
async def glove(message: types.message):
    """Обработчик для режима «Дуэль!»"""
    users = await db.all_users()
    i_am = await db.get_user(message)
    name = i_am['username']
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    buttons = []
    for user in users:
        if user['username'] != i_am['username']:
            buttons.append(f'/duel @{user["username"]}')
    if len(buttons) != 0:
        keyboard.add(*buttons)
        text = (
            'выберите противника, воспользуйтесь командой формата "/duel @username" '
            'если искомый противник отсутствует в списке, или попросите  зарегестрироваться с помощью «/registrate»'
                )
        await message.answer(f"@{name} {text}", reply_markup=keyboard)
    else:
        text = (
            'в списке нет зарегестрированных пользователей '
            'воспользуйтесь командой формата "/duel @username" для вызова на дуэль '
            'или попросите зарегестрироваться с помощью «/registrate»'
                )
        keyboard = types.ReplyKeyboardRemove()
        await message.answer(f"@{name} {text}", reply_markup=keyboard)


@dp.message_handler(Text(equals="Турнир!"))
async def cup_invitation(message: types.message):
    """Функция и обработчик для режима «Турнир!»"""
    await db.get_user(message)
    keyboard = types.ReplyKeyboardRemove()
    text = 'объявил турнир по камень - ножницы - бумага турнир начнется через'
    await message.answer(
        f"{message.from_user.username} {text} {game.timer_before_start} секунд", reply_markup=keyboard
                        )
    # Массив кнопок для инлайн клавиатуры
    buttons = [
        types.InlineKeyboardButton(text='Принять', callback_data='accept_cup'),
        types.InlineKeyboardButton(text='Отказаться', callback_data='cancel_cup')
        ]
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(*buttons)
    game.tour_baner = await message.answer(
        f"Вам предлагают принять участие в турнире камень - ножницы - бумага",
        reply_markup=keyboard
        )
    await asyncio.sleep(game.timer_before_start)
    await bot.delete_message(game.tour_baner.chat.id, game.tour_baner.message_id)
    game.tour_baner = await game.new_tour()


@dp.message_handler(Text(equals="Отмена!"))
async def glove(message: types.message):
    pass

@dp.callback_query_handler(Text(equals='accept_cup'))
async def fingers(call: types.CallbackQuery):
    """Обработчик согласия на турнир."""
    await db.get_user(call.message)
    in_list = await game.new_challenger(call.from_user.username)
    if in_list:
        await call.answer('Ты в игре!', show_alert=True)
    else:
        await call.answer('Ты уже в списке', show_alert=True)


@dp.callback_query_handler(Text(equals='cancel_cup'))
async def fingers(call: types.CallbackQuery):
    """Обработчик отказа на участие в турнире"""
    in_list = await game.del_challenger(call.from_user.username)
    if in_list:
        await call.answer('Ты удален из списка игроков', show_alert=True)
    else:
        await call.answer('Как хочешь!', show_alert=True)


@dp.message_handler(content_types='text')
async def choise(message: types.message):
    """Обработчик сообщений пользователя на апредмет нахождения команды по шаблону вызова на дуэль"""
    match = re.search(r'^/duel @\w+', message.text)
    if match:
        user1 = message.from_user.username
        user2 = message.text.partition('@')[2].partition(' ')[0]
        game.tour_challengers.append(user1)
        game.tour_challengers.append(user2)
        game.tour_baner = message
        await game.new_tour()


@dp.callback_query_handler(Text(equals=["Камень", "Ножницы", "Бумага"]))
async def fingers(call: types.CallbackQuery):
    """Обработчик Сообщения C Фигурой"""
    result = await game.check_and_set_choise(call.from_user.username, call.data, call.message)
    await call.answer(result['text'], show_alert=True)
    await db.set_user(call.from_user.id, update={'total_duels': 1})
    if result['num_of_choise'] == 2:
        winner = await game.winner_in_duel(call.message)
        # проверка на ничью, если ничья, изменение сообщения Для повторного запроса дуэли
        if winner['winner'] is None:
            duel = await game.get_duel(call.message)
            await duel.reset_duel()
            await call.message.edit_text('Ничья, выберите еще раз')
        else:
            # если победитель в дуэли определен
            await call.answer(winner['text'])
            await db.set_by_username(winner['winner'], update={'win_in_duels': 1})
            if len(game.duels) == 0:
                # Если дуэль последняя в списке дуэлей
                if len(game.tour_challengers) > 0:
                    # Если в списке участников кто-то есть (дуэль была последней в не последнем туре)
                    game.tour_challengers.append(winner['winner'])
                    await game.new_tour()
                else:
                    # Если в списке участников никого(дуэль была последней в последнем туре)
                    if game.tour_mark:
                        # если турнир
                        await db.set_by_username(winner['winner'], update={'win_in_tournaments': 1})
                    else:
                        # если не турнир
                        await db.set_by_username(winner['winner'], update={'win_in_duels': 1})
                    await game.game_clear()

            else:
                game.tour_challengers.append(winner['winner'])


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
