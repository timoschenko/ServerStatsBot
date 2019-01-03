from datetime import datetime
from subprocess import Popen, PIPE, STDOUT
import os
import operator
import collections
# import sys
import time
# import threading
# import random
import traceback


try:
    from telegram import ChatAction, ReplyMarkup, ParseMode
    from telegram.ext import Filters, Updater, MessageHandler
except ImportError:
    print('telegram module is not found!')
    print('Use the command below to install it:')
    print('   root $ pip3 install python-telegram-bot')
    print("\nCan't continue without the module! Exit..")
    exit(3)


try:
    from tokens import telegrambot, adminchatid, proxy, enable_shell_command
except ImportError:
    print('ServerStatsBot is not configured!')
    print('Create your an own token.py file just like token.py_example')
    print('  and specify a token and chat_id.')
    print("\nCan't continue without the module! Exit..")
    exit(3)


try:
    import matplotlib
    # has to be before any other matplotlibs imports to set a "headless" backend
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib = None
    plt = None

    print('matplotlib is not found.')
    print('Use the command below to install it:')
    print('   root $ apt install python3-matplotlib')
    print("\nLet's continue, but some features will not be available")


try:
    import psutil
except ImportError:
    psutil = None

    print('Use the command below to install it:')
    print('   root $ apt install python3-psutil')
    print('or')
    print('   root $ pip3 install psutil')
    print("\nLet's continue, but some features will not be available")


STRINGS = {
    'alert_bootup': "_I'm up!_",
    'alert_shutdown': "_I'm shutting down!_",
    'button_stop': 'Stop',
    'error': 'Something went wrong',
    'reply_chat_id': "Hello the stranger! Your id is `{chat_id}`. Please send the id to bot's administration",
    'reply_help': 'Hello! Your id is `{chat_id}`.',
    'reply_stopped': 'Return to normal mode',
    'reply_set_poll_interval': 'Send me a new polling interval in seconds? (higher than 10)',
    'reply_set_poll_interval_done': 'All set!',
    'reply_set_poll_interval_error': 'Please send a proper numeric value higher than 10.',
    'reply_shell_cmd': 'Send me a shell command to execute',
    'reply_shell_cmd_empty': 'No output.',
    'reply_set_threshold': 'Send me a new memory threshold to monitor?',
    'reply_set_threshold_done': 'All set!',
    'reply_set_threshold_error': 'Please send a proper numeric value below 100.',
    'graph_title': 'Memory Usage Graph',
    'graph_x': 'Last {:.2f} hours',
    'graph_y': '% Used',
    'graph_threshold': 'Threshold: {}%',
    'stats_onilne_hours': 'Uptime is _{:.1f}_ Hours',
    'stats_memory_total': 'Total memory: _{:.2f} GB_',
    'stats_memory_available': 'Available memory: _{:.2f} GB_',
    'stats_memory_used': 'Used memory: _{}%_',
    'stats_disk_used': 'Disk used: _{}%_',
    'alert_low_memory': 'CRITICAL! LOW MEMORY!'
}

memorythreshold = 85  # If memory usage more this %
poll = 300  # seconds
temp_graph_path = 'graph.png'

shellexecution = []
timelist = []
memlist = []
xaxis = []
settingmemth = []
setpolling = []
graphstart = datetime.now()

default_kwargs = {'parse_mode': ParseMode.MARKDOWN, 'disable_web_page_preview': True}
stopmarkup = {'keyboard': [[STRINGS['button_stop']]]}
hide_keyboard = {'hide_keyboard': True}
help_markup = {'keyboard': [['/stats'], ['/memgraph']]}

spamguard = 0

def clearall(chat_id):
    if chat_id in shellexecution:
        shellexecution.remove(chat_id)
    if chat_id in settingmemth:
        settingmemth.remove(chat_id)
    if chat_id in setpolling:
        setpolling.remove(chat_id)

def plotmemgraph(memlist, xaxis, tmperiod):
    assert plt is not None, 'install matplotlib'

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
    plt.savefig(temp_graph_path)
    plt.close()
    f = open(temp_graph_path, 'rb')  # some file on local disk
    return f


def on_message(bot, upd):
    chat_id = upd.message.chat.id
    message = upd.message.text
    print('Message from the {} id: "{}"'.format(chat_id, message))

    # TODO: Move to the command_handler function
    global spamguard
    now = time.time()
    if message in ['/start', '/help'] and (now - spamguard) > 30:
        spamguard = now

        bot.send_chat_action(chat_id, ChatAction.TYPING)
        replymsg = STRINGS['reply_chat_id'].format(chat_id=chat_id) \
                if chat_id not in adminchatid else                  \
                STRINGS['reply_help'].format(chat_id=chat_id)

        bot.send_message(chat_id, replymsg, **default_kwargs)
        return

    if chat_id not in adminchatid:
        return

    try:
        command_handler(bot, upd, chat_id, message)
    except Exception:
        traceback.print_exc()

        bot.send_message(chat_id, STRINGS['error'], **default_kwargs)


def command_handler(bot, upd, chat_id, message):
    if message == STRINGS['button_stop']:
        clearall(chat_id)
        bot.send_message(chat_id, STRINGS['reply_stopped'], reply_markup=hide_keyboard, **default_kwargs)

    # NOTE: Indirect shell access
    elif chat_id in shellexecution:
        assert enable_shell_command, 'Security break!'
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        p = Popen(message, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.read()
        if not output:
            bot.send_message(chat_id, output, **default_kwargs)
        else:
            bot.send_message(chat_id, STRINGS['reply_shell_cmd_empty'], **default_kwargs)
    elif enable_shell_command and message == "/shell":
        bot.send_message(chat_id, STRINGS['reply_shell_cmd'],
                reply_markup=stopmarkup, **default_kwargs)
        shellexecution.append(chat_id)

    # NOTE: Configuration
    elif message == '/setpoll' and chat_id not in setpolling:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        setpolling.append(chat_id)
        bot.send_message(chat_id, STRINGS['reply_set_poll_interval'],
                reply_markup=stopmarkup, **default_kwargs)
    elif chat_id in setpolling:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        try:
            newpoll = int(message)  # raise ValueError if can't convert
            if newpoll < 10:
                raise ValueError('%d is too small' % newpoll)

            global poll
            poll = newpoll
            bot.send_message(chat_id, STRINGS['reply_set_poll_interval_done'],
                    reply_markup=hide_keyboard, **default_kwargs)
            clearall(chat_id)
        except ValueError:
            bot.send_message(chat_id, STRINGS['reply_set_poll_interval_error'], **default_kwargs)
    elif message == "/setmem" and chat_id not in settingmemth:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        settingmemth.append(chat_id)
        bot.send_message(chat_id, STRINGS['reply_set_threshold'], reply_markup=stopmarkup,
                **default_kwargs)

    elif chat_id in settingmemth:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        try:
            newmem = int(message)
            if newmem > 100:
                raise ValueError('%d is too small' % newmem)

            global memorythreshold
            memorythreshold = newmem
            bot.send_message(chat_id, STRINGS['reply_set_threshold_done'], reply_markup=hide_keyboard, **default_kwargs)
            clearall(chat_id)
        except ValueError:
            bot.send_message(chat_id, STRINGS['reply_set_threshold_error'], **default_kwargs)

    # NOTE: Singleshot commands below
    elif message == '/stats' and psutil is not None:
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
            except Exception:
                traceback.print_exc()
        sortedprocs = sorted(procs.items(), key=operator.itemgetter(1), reverse=True)
        pidsreply = '\n'.join("`%s` _%.2f%%_" % (proc[0], proc[1]) for proc in sortedprocs)
        reply = '\n'.join((timedif,
            memtotal,
            memavail,
            memuseperc,
            diskused,
            '\n',
            pidsreply,))
        bot.send_message(chat_id, reply.strip(), **default_kwargs)
    elif message == '/memgraph' and matplotlib is not None:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        tmperiod = STRINGS['graph_x'].format((datetime.now() - graphstart).total_seconds() / 3600)
        with plotmemgraph(memlist, xaxis, tmperiod) as photo:
            bot.sendPhoto(chat_id, photo)


assert os.geteuid() != 0, 'Security break! Do not run the bot as root/super user!'

print('> Connect to Telegram servers..')
TOKEN = telegrambot
if proxy:
    updater = Updater(TOKEN, request_kwargs=proxy)
else:
    updater = Updater(TOKEN)

on_message_handler = MessageHandler(Filters.text | Filters.command, on_message)
updater.dispatcher.add_handler(on_message_handler)
updater.start_polling()
lastpoll = 0
xx = 0
print('> Ready to work!')
for adminid in adminchatid:
    updater.bot.send_message(adminid, STRINGS['alert_bootup'], **default_kwargs)

try:
    # Keep the program running.
    while True:
        timenow = time.time()
        if (timenow - lastpoll) >= poll:
            try:
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
                        updater.bot.send_message(adminid, "{}\n{}".format(STRINGS['alert_low_memory'], memavail),
                                **default_kwargs)

                    if matplotlib is not None:
                        with plotmemgraph(memlist, xaxis, tmperiod) as photo:
                            for adminid in adminchatid:
                                updater.bot.send_photo(adminid, photo)
            except Exception:
                traceback.print_exc()
            finally:
                lastpoll = timenow

        time.sleep(10)
except (SystemExit, KeyboardInterrupt,):
    print('> Catch Exit')
finally:
    try:
        for adminid in adminchatid:
            updater.bot.send_message(adminid, STRINGS['alert_shutdown'], **default_kwargs)
    finally:
        print('> Stop polling...')
        updater.stop()
