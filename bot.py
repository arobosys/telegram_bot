#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import config
import telebot
import schedule
import threading
import re
import time

from telebot import types


subscribers = []
subscriptions_file = "./subscriptions"
alert_time_1h = "14:00"
alert_time_10min = "14:50"
alert_time_start = "15:00"


def jira_gen_task(tname):
    return str(tname) + ': https://arobosys.atlassian.net/browse/' + str(tname)

dfl_pair = lambda group : (group + '-', re.compile(group + '[ -]?(\d+)', re.IGNORECASE))
jira_task_regex = list(map(dfl_pair, ['AV', 'AG', 'SITE', 'RD']))
def jira_hdl_trytask(prefix, regex, msg_text):
    return "\n".join(map(lambda num: jira_gen_task(prefix + str(num)), regex.findall(msg_text)))
def jira_hdl(message):
    return "\n".join(map(lambda p: jira_hdl_trytask(*p, message.text), jira_task_regex))

keyboard = types.InlineKeyboardMarkup()
okButton = types.InlineKeyboardButton(text="Буду", callback_data="ok")
textButton = types.InlineKeyboardButton(text="Текст", callback_data="half_ok")
denyButton = types.InlineKeyboardButton(text="Не буду", callback_data="fail")
keyboard.add(okButton, textButton, denyButton);

poker_marks = {}
numbers_regex = re.compile('(\d+)')
def poker_hdl(message):
    chat_id = message.chat.id
    msg_text = message.text
    from_id = message.from_user.id
    answ = ''
    pm = poker_marks.get(chat_id)

    if msg_text.find('!poker') == 0:
        answ += "Партия начата! Оценки: 1 3 5 8 13. "
        if pm != None:
            answ += "Предыдущая партия сброшена. "
        answ += "\n"
        poker_marks[chat_id] = {}
    elif msg_text.find('!sum') == 0:
        if pm == None:
            answ += "Партия не начата, нечего суммировать. См: !poker"
        elif len(pm) == 0:
            answ += "Партия завершена, сыграна впустую."
            poker_marks.pop(chat_id, None)
        else:
            answ += "Партия завершена. Среднее: " + str(sum(pm.values()) / len(pm))
            poker_marks.pop(chat_id, None)
    elif pm != None:
        try:
            pm[from_id] = float(numbers_regex.findall(msg_text)[0])
        except IndexError:
            answ = "Че ты несешь-то вообще? Число напиши"

    return answ

def load_subscribers():
    global subscribers
    with open(subscriptions_file, 'r') as fl:
        subscribers = list(map(int, fl.read().splitlines()))


def store_subscribers():
    global subscribers
    with open(subscriptions_file, 'w') as fl:
        fl.write("\n".join(map(str, subscribers)))

def subscr_hdl(message):
    chat_id = message.chat.id
    msg_text = message.text
    answ = ''
    global subscribers
    if msg_text.find('!subscribe') != 0:
        return ''

    if chat_id in subscribers:
        answ = "Сук, да ты и так уже подписан!"
    else:
        answ = "Подписка оформлена."
        subscribers += [chat_id]
        store_subscribers()
    return answ


def unsubscr_hdl(message):
    chat_id = message.chat.id
    msg_text = message.text
    answ = ''
    global subscribers
    if msg_text.find('!unsubscribe') != 0:
        return ''

    if not int(chat_id) in subscribers:
        answ = "Сук, да я смотрю ты и не подписан!"
    else:
        answ = "Подписка отменена."
        subscribers.remove(chat_id)
        store_subscribers()
    return answ


def send_alerts(alert_msg, keyboard):    
    for chat_id in subscribers:
        bot.send_message(chat_id, alert_msg, reply_markup=keyboard)

participants = {}

def start_alert():
    global participants
    alive = []
    text = []
    absent = []
    print(participants)
    for key, value in participants.items():
        if value == "ok":
            alive.append(key)
        elif value == "half_ok":
            text.append(key)
        elif value == "fail":
            absent.append(key)
    send_alerts("Стартуем!\n" + "Обещали прийти: " + ' '.join(alive) + "\n" + 
        "В текстомов режиме: " + ' '.join(text) + "\n" + 
        "Не придут: " + ' '.join(absent), None)
    participants = []

def send_alerts_thr():
    print("Alert sending thread started.")

    schedule.every().day.at(alert_time_1h).do(lambda: send_alerts("Через час дебютнём!", None))
    schedule.every().day.at(alert_time_10min).do(lambda: send_alerts("Через 10 мин дебютнём!", keyboard))
    schedule.every().day.at(alert_time_start).do(start_alert)

    while 1:
        schedule.run_pending()
        time.sleep(1)


# # # # # # # # # # # # # # # # # # # # # # # # # # # #

bot = telebot.TeleBot(config.token)
bot_handlers = [poker_hdl, subscr_hdl, unsubscr_hdl, jira_hdl]

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    global participants
    if call.message:
        name = call.from_user.first_name
        participants[name] = call.data

@bot.message_handler(content_types=["text"])
def handler(message):
    print("RECV: " + message.text)
    msg = ''.join(map(lambda h: h(message), bot_handlers)).strip()
    
    if msg != "":
        bot.send_message(message.chat.id, msg)

if __name__ == '__main__':
    load_subscribers()
    alert_thread = threading.Thread(target=send_alerts_thr)
    alert_thread.start()
    while True:
        try:
            bot.polling(none_stop=True)
        except requests.exceptions.ConnectionError as e:
            print >> sys.stderr, str(e)
            time.sleep(15)
