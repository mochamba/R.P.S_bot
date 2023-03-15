from aiogram import types
from pymongo import MongoClient
from os import getenv
from sys import exit



mongo_token = getenv("MONGO_TOKEN")
if not mongo_token:
    exit("Error - not MONGO_TOKEN token")


class DataBase:
    u"""Класс для работы с базой данных пользователей"""
    # Определение конструктора класса
    def __init__(self):
        #  Обращаемся к кластеру mongo приравниваем к в переменной cluster
        cluster = MongoClient(mongo_token)
        #  ПРиравниваем коллекцию к переменной users
        self.users = cluster.KMN.Users

#
    async def get_user(self, message: types.message):
        """Метод добавляющий пользователя отправившего сообщение  в базу, если его там нет
        И возвращающий запись пользователя, если он уже есть в базе."""
        user = self.users.find_one({"user_id": message.from_user.id})
        if user is not None:
            return user
        if message.from_user.username == '':
            username = message.from_user.full_name
        else:
            username = message.from_user.username
        # Структура словаря пользователи
        user = {
            'user_id': message.from_user.id,
            'username': username,
            'total_duels': 0,
            'win_in_duels': 0,
            'win_in_tournaments': 0
            }

        self.users.insert_one(user)
        return user

    async def set_user(self, user_id: int, update: dict):
        """Изменят запись о пользователе"""
        await self.set_user(user_id, update={'win_in_tournaments': 1})
        self.users.update_one({"user_id": user_id}, {"$inc": update})

    async def all_users(self):
        """Метод возвращающий все записи пользователей"""
        users = self.users.find({})
        return users

    async def set_by_username(self, username, update: dict):
        user = self.users.find_one({"username": username})
        name_of_user = user.username
        await self.set_user(name_of_user, update)


class Dueler:
    """Вспомогательный класс для хранения имени игрока и выбранной им фигуры"""
    def __init__(self, username):
        self.username = username
        self.finger_choise = None


class Duel:
    """Класс непосредственно представляющий из себя партию в камень - Ножницы - Бумага"""
    def __init__(self, *list_of_gamers: list):
        self.users = []
        self.message_banner = None
        for gamer in list_of_gamers:
            self.users.append(Dueler(gamer))
        self.choise_count = 0

    #  Функция отправляющая сообщение о дуэли
    async def duel_call(self, message: types.message):
        """Отправляет пользователю приглашение о выборе фигуры."""
        keyboard = types.ReplyKeyboardRemove()
        text = f'@{self.users[0].username} Вызывает на дуэль @{self.users[1].username}'
        await message.answer(text, reply_markup=keyboard)
        buttons = [
            types.InlineKeyboardButton(text="Камень", callback_data="Камень"),
            types.InlineKeyboardButton(text="Ножницы", callback_data="Ножницы"),
            types.InlineKeyboardButton(text="Бумага", callback_data="Бумага"),
            types.InlineKeyboardButton(text="Отказаться от дуэли", callback_data="Cancel")
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*buttons)
        self.message_banner = await message.answer('Сделайте свой выбор', reply_markup=keyboard)

    # Функция определения победителя
    async def get_winner(self) -> dict:
        """Метод для определения победителя в дуэли."""
        text = ''
        username1 = self.users[0].username
        username2 = self.users[1].username
        choise1 = self.users[0].finger_choise
        choise2 = self.users[0].finger_choise
        winner = ''
        if choise1 == choise2:
            text = f"Ничья {choise1} ({username1}) против {choise2} ({username2})"
            winner = None
        else:
            match choise1:
                case "Камень":
                    match choise2:
                        case "Ножницы":
                            text = f"Победил @{username1} {choise1} VS {choise2}"
                            winner = username1
                        case "Бумага":
                            text = f"Победил @{username2} {choise1} VS {choise2}"
                            winner = username2
                case "Ножницы":
                    match choise2:
                        case "Камень":
                            text = f"Победил @{username2} {choise1} VS {choise2}"
                            winner = username2
                        case "Бумага":
                            text = f"Победил @{username1} {choise1} VS {choise2}"
                            winner = username1
                case "Бумага":
                    match choise2:
                        case "Камень":
                            text = f"Победил @{username1}{choise1} VS {choise2}"
                            winner = username1
                        case "Ножницы":
                            text = f"Победил @{username2}{choise1} VS {choise2}"
                            winner = username2
        return {'text': text, 'winner': winner}

    async def reset_duel(self):
        """сброс состояния дуэли, для подготовки после ничьей"""
        self.choise_count = 0
        for user in self.users:
            user.finger_choise = None


class Game:
    """Класс для запуска дуэлей и турниров"""
    def __init__(self):
        self.duels = []
        self.timer_before_start = 20
        self.tour_challengers = []
        self.tour_baner = None
        self.tour_mark = False

    async def game_clear(self):
        self.duels.clear()
        self.tour_challengers.clear()
        self.tour_baner = None
        self.tour_mark = False

    async def new_challenger(self, username: str) -> bool:
        """Метод добавляющий нового игрока в список участников турнира. Возвращает True если участник только
        что добавлен и False если участник уже был в списке."""
        if username not in self.tour_challengers:
            self.tour_challengers.append(username)
            return True
        else:
            return False

    async def del_challenger(self, username: str) -> bool:
        """Метод удаляющий игрока из списка участников турнира.Возвращает True если участник только что удален
        и False если участника в списке и не было."""
        if username in self.tour_challengers:
            self.tour_challengers.remove(username)
            return True
        else:
            return False

    async def new_tour(self):
        """Метод проводящий турнир или одиночную дуэль(как частный метод турнира)"""
        flag = 0
        duel_list = []
        if len(self.tour_challengers) > 2:
            self.tour_mark = True
        for user in self.tour_challengers:
            duel_list.append(user)
            flag += 1
            if flag == 2:
                self.duels.append(Duel(*duel_list))
                self.tour_challengers = self.tour_challengers[2:]
                flag = 0
        if flag == 1:
            duel_list.clear()
        for duel in self.duels:
            await duel.duel_call(self.tour_baner)

    async def get_duel(self, message: types.message) -> Duel:
        """Метод предназначенный для поиска дуэли в списке дуэлей."""
        for duel in self.duels:
            if duel.message_banner.message_id == message.message_id:
                return duel

    async def check_and_set_choise(self, username: str, chosen_figure: str, message: types.message) -> dict:
        """Метод для проверки записи выбора пользователя  в конкретной дуэли"""
        desired_duel = await self.get_duel(message)
        for user in desired_duel.users:
            if user.username == username:
                if user.finger_choise is None:
                    user.finger_choise = chosen_figure
                    desired_duel.choise_count += 1
                    return {'text': f"Ты выбрал {chosen_figure}",
                            'num_of_choise': desired_duel.choise_count}
                else:
                    return {'text': 'Ты уже сделал свой выбор, второй раз низ-зя',
                            'num_of_choise': desired_duel.choise_count}

        return {'text': 'Иди своей дорогой сталкер, это не твой бой',
                        'num_of_choise': desired_duel.choise_count}

    async def winner_in_duel(self, message: types.Message):
        """Метод для определения победителя в дуэли"""
        duel = await self.get_duel(message)
        result = await duel.get_winner()
        self.duels.remove(duel)
        return result
