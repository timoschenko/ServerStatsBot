# pylint: disable=broad-except,global-statement,invalid-name,missing-docstring,fixme

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
    from telegram import ChatAction, ParseMode
    from telegram.ext import Filters, Updater, MessageHandler
except ImportError:
    print('telegram module is not found!')
    print('Use the command below to install it:')
    print('   root $ pip3 install python-telegram-bot')
    print("\nCan't continue without the module! Exit..")
    exit(3)


try:
    from tokens import adminchatid, proxy, enable_shell_command
    from tokens import telegrambot as TOKEN
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
    'reply_hello_access': "Please send the id to bot's administration to get access",
    'reply_hello_id': 'Hello the stranger! Your id is `{chat_id}`.',
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

ALERT_UPDATE_INTERVAL = 300  # seconds
GRAPH_START_TIME = datetime.now()
GRAPH_TEMP_FILE = 'graph.png'
GRAPH_X_AXIS = []
LAST_SPAM_COMMAND = 0
MENU_SETS_MEMTH = []
MENU_SETS_POLLING = []
MENU_SHELL = []
RAM_HISTORY = []
RAM_THRESHOLD = 85  # If memory usage more this %

DEFAULT_KWARGS = {'parse_mode': ParseMode.MARKDOWN, 'disable_web_page_preview': True}
MARKUP_STOP = {'keyboard': [[STRINGS['button_stop']]]}
MARKUP_HIDEKEYBOARD = {'hide_keyboard': True}


def clearall(chat_id):
    '''Return to main bot's main menu
    '''

    if chat_id in MENU_SHELL:
        MENU_SHELL.remove(chat_id)
    if chat_id in MENU_SETS_MEMTH:
        MENU_SETS_MEMTH.remove(chat_id)
    if chat_id in MENU_SETS_POLLING:
        MENU_SETS_POLLING.remove(chat_id)


def plotmemgraph(memlist, xaxis, tmperiod):
    '''Draw an image of RAM usage.

    Return an opened file object which must be closed after.

    * required metplotlib module
    '''
    # TODO: memory leak here!
    assert plt is not None, 'install matplotlib'

    # print(memlist)
    # print(xaxis)
    plt.xlabel(tmperiod)
    plt.ylabel(STRINGS['graph_y'])
    plt.title(STRINGS['graph_title'])
    plt.text(0.1 * len(xaxis),
             RAM_THRESHOLD + 2,
             STRINGS['graph_threshold'].format(RAM_THRESHOLD))

    memthresholdarr = [RAM_THRESHOLD] * len(xaxis)
    plt.plot(xaxis, memlist, 'b-', xaxis, memthresholdarr, 'r--')
    plt.axis([0, len(xaxis) - 1, 0, 100])
    plt.savefig(GRAPH_TEMP_FILE)
    plt.close()
    return open(GRAPH_TEMP_FILE, 'rb')  # some file on local disk


def on_message(bot, upd):
    '''Bot's messages handler (callback).

    Can be invoked only by Telegram's Updater.
    '''

    chat_id = upd.message.chat.id
    message = upd.message.text
    print('Message from the {} id: "{}"'.format(chat_id, message))

    # TODO: Move to the command_handler function
    global LAST_SPAM_COMMAND
    now = time.time()
    if message in ['/start', '/help'] and (now - LAST_SPAM_COMMAND) > 30:
        LAST_SPAM_COMMAND = now

        bot.send_chat_action(chat_id, ChatAction.TYPING)
        replymsg = STRINGS['reply_hello_id'].format(chat_id=chat_id)
        if chat_id not in adminchatid:
            replymsg += '\n'
            replymsg += STRINGS['reply_hello_access']

        bot.send_message(chat_id, replymsg, **DEFAULT_KWARGS)
        return

    if chat_id not in adminchatid:
        return

    try:
        command_handler(bot, upd, chat_id, message)
    except Exception:
        traceback.print_exc()

        bot.send_message(chat_id, STRINGS['error'], **DEFAULT_KWARGS)


def command_handler(bot, upd, chat_id, message):  # TODO: Too complex
    '''Bot's commands handler (callback).

    Can be invoked only by Bot's messages handler.
    '''

    if message == STRINGS['button_stop']:
        clearall(chat_id)
        bot.send_message(chat_id,
                         STRINGS['reply_stopped'],
                         reply_markup=MARKUP_HIDEKEYBOARD,
                         **DEFAULT_KWARGS)

    # NOTE: Indirect shell access
    elif chat_id in MENU_SHELL:
        assert enable_shell_command, 'Security break!'
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        p = Popen(message, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.read()
        bot.send_message(chat_id,
                         output if output else STRINGS['reply_shell_cmd_empty'],
                         **DEFAULT_KWARGS)

    elif enable_shell_command and message == "/shell":
        bot.send_message(chat_id,
                         STRINGS['reply_shell_cmd'],
                         reply_markup=MARKUP_STOP,
                         **DEFAULT_KWARGS)

        MENU_SHELL.append(chat_id)

    # NOTE: Configuration
    elif message == '/setpoll' and chat_id not in MENU_SETS_POLLING:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        MENU_SETS_POLLING.append(chat_id)
        bot.send_message(chat_id,
                         STRINGS['reply_set_poll_interval'],
                         reply_markup=MARKUP_STOP,
                         **DEFAULT_KWARGS)

    elif chat_id in MENU_SETS_POLLING:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        try:
            val = int(message)  # raise ValueError if can't convert
            if val < 10:
                raise ValueError('%d is too small' % val)

            global ALERT_UPDATE_INTERVAL
            ALERT_UPDATE_INTERVAL = val
            bot.send_message(chat_id,
                             STRINGS['reply_set_poll_interval_done'],
                             reply_markup=MARKUP_HIDEKEYBOARD,
                             **DEFAULT_KWARGS)

            clearall(chat_id)
        except ValueError:
            bot.send_message(chat_id, STRINGS['reply_set_poll_interval_error'], **DEFAULT_KWARGS)

    elif message == "/setmem" and chat_id not in MENU_SETS_MEMTH:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        MENU_SETS_MEMTH.append(chat_id)
        bot.send_message(chat_id,
                         STRINGS['reply_set_threshold'],
                         reply_markup=MARKUP_STOP,
                         **DEFAULT_KWARGS)

    elif chat_id in MENU_SETS_MEMTH:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        try:
            newmem = int(message)
            if newmem > 100:
                raise ValueError('%d is too small' % newmem)

            global RAM_THRESHOLD
            RAM_THRESHOLD = newmem
            bot.send_message(chat_id,
                             STRINGS['reply_set_threshold_done'],
                             reply_markup=MARKUP_HIDEKEYBOARD,
                             **DEFAULT_KWARGS)

            clearall(chat_id)
        except ValueError:
            bot.send_message(chat_id, STRINGS['reply_set_threshold_error'], **DEFAULT_KWARGS)

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
        procs = {}
        for pid in psutil.pids():
            p = psutil.Process(pid)
            try:
                pmem = p.memory_percent()
                if pmem > 0.5:
                    proc_name = p.name()
                    if proc_name not in procs:
                        procs[proc_name] = 0

                    procs[proc_name] += pmem
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
        bot.send_message(chat_id, reply.strip(), **DEFAULT_KWARGS)
    elif message == '/memgraph' and matplotlib is not None:
        bot.send_chat_action(chat_id, ChatAction.TYPING)
        tmperiod = STRINGS['graph_x'].format((datetime.now()
                                              - GRAPH_START_TIME).total_seconds() / 3600)
        with plotmemgraph(RAM_HISTORY, GRAPH_X_AXIS, tmperiod) as photo:
            bot.sendPhoto(chat_id, photo)


def alert_handle(bot):
    '''Bot's handle of alerts

    Need to keep the bot at running state
    '''

    global RAM_HISTORY

    try:
        memck = psutil.virtual_memory()
        mempercent = memck.percent
        if len(RAM_HISTORY) > 300:
            memq = collections.deque(RAM_HISTORY)
            memq.append(mempercent)
            memq.popleft()

            RAM_HISTORY = memq
            RAM_HISTORY = list(RAM_HISTORY)  # FIXME: deep copy
        else:
            xaxis = None
            try:
                xaxis = GRAPH_X_AXIS[-1]
            except LookupError:
                xaxis = 0

            GRAPH_X_AXIS.append(xaxis)
            RAM_HISTORY.append(mempercent)

        if mempercent > RAM_THRESHOLD:
            memavail = STRINGS['stats_memory_available'].format(memck.available / 1000000000)
            graphend = datetime.now()
            tmperiod = STRINGS['graph_x'].format(
                (graphend - GRAPH_START_TIME).total_seconds() / 3600)

            for adminid in adminchatid:
                bot.send_message(adminid,
                                 "{}\n{}".format(STRINGS['alert_low_memory'],
                                                 memavail),
                                 **DEFAULT_KWARGS)

            if matplotlib is not None:
                with plotmemgraph(RAM_HISTORY, GRAPH_X_AXIS, tmperiod) as photo:
                    for adminid in adminchatid:
                        bot.send_photo(adminid, photo)
    except Exception:
        traceback.print_exc()


def main():  # TODO: Too complex
    '''Entery point of application
    '''

    assert os.geteuid() != 0, 'Security break! Do not run the bot as root/super user!'

    print('> Connect to Telegram servers..')
    updater = Updater(TOKEN,
                      request_kwargs=proxy if proxy else None)

    on_message_handler = MessageHandler(Filters.text | Filters.command, on_message)
    updater.dispatcher.add_handler(on_message_handler)
    updater.start_polling()
    print('> Ready to work!')
    for adminid in adminchatid:
        updater.bot.send_message(adminid, STRINGS['alert_bootup'], **DEFAULT_KWARGS)

    try:
        lastpoll = 0
        while True:
            timenow = time.time()
            if (timenow - lastpoll) >= ALERT_UPDATE_INTERVAL:
                try:
                    alert_handle(updater.bot)
                finally:
                    lastpoll = timenow

            time.sleep(10)
    except (SystemExit, KeyboardInterrupt,):
        print('> Catch Exit')
    finally:
        try:
            for adminid in adminchatid:
                updater.bot.send_message(adminid, STRINGS['alert_shutdown'], **DEFAULT_KWARGS)
        finally:
            print('> Stop polling...')
            updater.stop()


if __name__ == '__main__':
    main()
