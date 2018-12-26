from tokens import *
import matplotlib
matplotlib.use("Agg") # has to be before any other matplotlibs imports to set a "headless" backend
import matplotlib.pyplot as plt
import psutil
from datetime import datetime
from subprocess import Popen, PIPE, STDOUT
import operator
import collections
# import sys
import time
# import threading
# import random
import telegram
from telegram import ChatAction, ReplyMarkup
from telegram.ext import Filters, Updater

STRINGS = {
    'button_stop': 'Stop',
    'reply_stopped': 'All operations stopped.',
    'reply_set_poll_interval': 'Send me a new polling interval in seconds? (higher than 10)',
    'reply_set_poll_interval_done': 'All set!',
    'reply_set_poll_interval_error': 'Please send a proper numeric value higher than 10.',
    'reply_shell_cmd': 'Send me a shell command to execute',
    'reply_shell_cmd_empty': 'No output.',
    'reply_set_threshold': 'Send me a new memory threshold to monitor?',
    'reply_set_threshold_done': 'All set!',
    'reply_set_threshold_error': 'Please send a proper numeric value below 100.',
    'graph_title': 'Memory Usage Graph',
    'graph_x': 'Last %.2f hours',
    'graph_y': '% Used',
    'graph_threshold': 'Threshold: {} %',
    'stats_onilne_hours': 'Online for: {:.1f} Hours',
    'stats_memory_total': 'Total memory: {:.2f} GB ',
    'stats_memory_available': 'Available memory: {:.2f} GB',
    'stats_memory_used': 'Used memory: {} %',
    'stats_disk_used': 'Disk used: {} %',
    'alert_low_memory': 'CRITICAL! LOW MEMORY!'
}

memorythreshold = 85  # If memory usage more this %
poll = 300  # seconds

shellexecution = []
timelist = []
memlist = []
xaxis = []
settingmemth = []
setpolling = []
graphstart = datetime.now()

stopmarkup = {'keyboard': [[STRINGS['button_stop']]]}
hide_keyboard = {'hide_keyboard': True}

def clearall(chat_id):
    if chat_id in shellexecution:
        shellexecution.remove(chat_id)
    if chat_id in settingmemth:
        settingmemth.remove(chat_id)
    if chat_id in setpolling:
        setpolling.remove(chat_id)

def plotmemgraph(memlist, xaxis, tmperiod):
    # print(memlist)
    # print(xaxis)
    plt.xlabel(tmperiod)
    plt.ylabel(STRINGS['graph_y'])
    plt.title(STRINGS['graph_title'])
    plt.text(0.1*len(xaxis), memorythreshold+2, STRINGS['graph_threshold'].format(memorythreshold))
    memthresholdarr = []
    for xas in xaxis:
        memthresholdarr.append(memorythreshold)
    plt.plot(xaxis, memlist, 'b-', xaxis, memthresholdarr, 'r--')
    plt.axis([0, len(xaxis)-1, 0, 100])
    plt.savefig('/tmp/graph.png')
    plt.close()
    f = open('/tmp/graph.png', 'rb')  # some file on local disk
    return f


def on_message(bot, upd):
    chat_id = upd.message.chat.id
    message = upd.message.text
    print('Message from {}:\n{}\n'.format(chat_id, message))

    if chat_id not in adminchatid:
        return

    if message == '/stats' and chat_id not in shellexecution:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boottime = datetime.fromtimestamp(psutil.boot_time())
        now = datetime.now()
        timedif = STRINGS['stats_onilne_hours'].format(((now - boottime).total_seconds()) / 3600)
        memtotal = STRINGS['stats_memory_total'].format(memory.total / 1000000000)
        memavail = STRINGS['stats_memory_available'].format(memory.available / 1000000000)
        memuseperc = STRINGS['stats_memory_used'].format(memory.percent)
        diskused = STRINGS['stats_disk_used'].format(disk.percent)
        pids = psutil.pids()
        pidsreply = ''
        procs = {}
        for pid in pids:
            p = psutil.Process(pid)
            try:
                pmem = p.memory_percent()
                if pmem > 0.5:
                    if p.name() in procs:
                        procs[p.name()] += pmem
                    else:
                        procs[p.name()] = pmem
            except:
                print("Hm")
        sortedprocs = sorted(procs.items(), key=operator.itemgetter(1), reverse=True)
        for proc in sortedprocs:
            pidsreply += proc[0] + " " + ("%.2f" % proc[1]) + " %\n"
        reply = timedif + "\n" + \
                memtotal + "\n" + \
                memavail + "\n" + \
                memuseperc + "\n" + \
                diskused + "\n\n" + \
                pidsreply
        bot.send_message(chat_id, reply, disable_web_page_preview=True)
    elif message == STRINGS['button_stop']:
        clearall(chat_id)
        bot.send_message(chat_id, STRINGS['reply_stopped'], reply_markup=hide_keyboard)
    elif message == '/setpoll' and chat_id not in setpolling:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        setpolling.append(chat_id)
        bot.send_message(chat_id, STRINGS['reply_set_poll_interval'], reply_markup=stopmarkup)
    elif chat_id in setpolling:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        try:
            global poll
            poll = int(message)
            if poll > 10:
                bot.send_message(chat_id, STRINGS['reply_set_poll_interval_done'])
                clearall(chat_id)
            else:
                1/0
        except:
            bot.send_message(chat_id, STRINGS['reply_set_poll_interval_error'])
    elif message == "/shell" and chat_id not in shellexecution:
        bot.send_message(chat_id, STRINGS['reply_shell_cmd'], reply_markup=stopmarkup)
        shellexecution.append(chat_id)
    elif message == "/setmem" and chat_id not in settingmemth:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        settingmemth.append(chat_id)
        bot.send_message(chat_id, STRINGS['reply_set_threshold'], reply_markup=stopmarkup)
    elif chat_id in settingmemth:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        try:
            global memorythreshold
            memorythreshold = int(message)
            if memorythreshold < 100:
                bot.send_message(chat_id, STRINGS['reply_set_threshold_done'])
                clearall(chat_id)
            else:
                1/0
        except:
            bot.send_message(chat_id, STRINGS['reply_set_threshold_error'])

    elif chat_id in shellexecution:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        p = Popen(message, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.read()
        if output != b'':
            bot.send_message(chat_id, output, disable_web_page_preview=True)
        else:
            bot.send_message(chat_id, STRINGS['reply_shell_cmd_empty'], disable_web_page_preview=True)
    elif message == '/memgraph':
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        tmperiod = STRINGS['graph_x'].format((datetime.now() - graphstart).total_seconds() / 3600)
        bot.sendPhoto(chat_id, plotmemgraph(memlist, xaxis, tmperiod))



TOKEN = telegrambot

updater = Updater(TOKEN)
updater.dispatcher.add_handler(on_message, Filters.text)
updater.start_polling()
tr = 0
xx = 0
# Keep the program running.
while 1:
    if tr == poll:
        tr = 0
        timenow = datetime.now()
        memck = psutil.virtual_memory()
        mempercent = memck.percent
        if len(memlist) > 300:
            memq = collections.deque(memlist)
            memq.append(mempercent)
            memq.popleft()
            memlist = memq
            memlist = list(memlist)
        else:
            xaxis.append(xx)
            xx += 1
            memlist.append(mempercent)
        memfree = memck.available / 1000000
        if mempercent > memorythreshold:
            memavail = STRINGS['stats_memory_available'].format(memck.available / 1000000000)
            graphend = datetime.now()
            tmperiod = STRINGS['graph_x'].format((graphend - graphstart).total_seconds() / 3600)
            for adminid in adminchatid:
                updater.bot.send_message(adminid, "{}\n{}".format(STRINGS['alert_low_memory'], memavail)
                updater.bot.send_photo(adminid, plotmemgraph(memlist, xaxis, tmperiod))
    time.sleep(10)  # 10 seconds
    tr += 10
