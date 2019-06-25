import curses, curses.panel
import sys

sys.path.insert(0, '../../../Collector/skipper-collector/') # TODO WARNING this only works on my computer
from app_hierarchy import Application

default_offset_x = 2
default_offset_y = 2

# def suppress_stdout():
#     with open(os.devnull, "w") as devnull:
#         old_stdout = sys.stdout
#         sys.stdout = devnull
#         try:
#             yield
#         finally:
#             sys.stdout = old_stdout

def create_window(height, width, begin_y, begin_x):
    return curses.newwin(height, width, begin_y, begin_x)

def create_panel_in_window(y, x, window):
    h,w = window.getmaxyx()
    win = window.derwin(h-4, w-4, y, x)
    win.erase()
    # win.box()

    panel = curses.panel.new_panel(win)
    return win, panel

def print_center(window, text_lines):
    # window.clear()
    h, w = window.getmaxyx()
    for i, line in enumerate(text_lines):
        x = w // 2 - len(line) // 2
        y = h // 2 - len(text_lines) // 2 + i
        window.addstr(y, x, line)
    window.refresh()

def initialize(app_objects, figlet):
    # initialize and set terminal settings (not necessary with wrapper)
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    curses.curs_set(0)

    loading(stdscr, figlet)
    app_jsons = get_app_info(app_objects)

    return stdscr, app_jsons

def loading(stdscr, figlet):
    stdscr.erase()
    print_center(stdscr, figlet + ["Loading cluster info from kube-config..."])

def get_app_info(app_objects):
    app_jsons = {}
    for app in app_objects.keys():
        app_objects[app].getGraph()
        app_jsons[app] = app_objects[app].generate_dicts()
    return app_jsons

def terminate(stdscr):
    # reverse terminal settings
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()

    # restore terminal to original operating mode
    curses.endwin()

def get_abbrv(type):
    type_abbrv = {'Application': 'App',
                  'Deployable': 'Dpb',
                  'Deployment': 'Dpm',
                  'Service': 'Svc',
                  'ReplicaSet': 'Rs',
                  'Pod': 'Po',
                  'Namespace': 'Ns',
                  'Cluster': 'Clus',
                  'Node': 'No',
                  'StatefulSet': 'Sts',
                  'DaemonSet': 'Ds',
                  'Container': 'Cont',
                  'Helm': 'Helm'
                  }
    return type_abbrv[type]

# TODO intended to combine update yaml, logs, description, events
def update_info(window, pad, app, current_resource, info_type):
    return

def update_yaml(window, pad, app, current_resource):
    window.erase()
    window.box()
    window.addstr(2, 2, "Yaml for " + current_resource.get_name())
    window.refresh()
    h, w = window.getmaxyx()
    y, x = window.getbegyx()

    try:
        yaml = app.getYaml(current_resource.get_type(), current_resource.get_name())
    except:
        yaml = "Yaml not found"

    # yaml_wrapped = textwrap.wrap(yaml, width=w)
    # text_file = open("yaml.txt", "w")
    # text_file.write("\n".join(yaml))
    # text_file.close()

    pad_text = yaml
    temp = 0
    for i in yaml.split("\n"):
        if len(i) > w:
            temp += len(i) // w
    extra_lines = temp

    pad.erase()
    pad.addstr(0, 0, yaml)

    pad.refresh(0, 0, y + 4, x + 2, y + h - 2, x + w - 2)

    window.refresh()
    return pad_text, extra_lines

def update_logs(window, pad, app, current_resource):
    window.erase()
    window.box()

    window.addstr(2, 2, "Logs for " + current_resource.get_name())
    window.refresh()
    h, w = window.getmaxyx()
    y, x = window.getbegyx()

    try:
        logs = app.getLogs(current_resource.get_name())
    except:
        logs = "Logs not found"

    pad_text = logs
    temp = 0
    for i in logs.split("\n"):
        if len(i) > w:
            temp += len(i) // w
    extra_lines = temp

    pad.erase()
    pad.addstr(0, 0, logs)

    pad.refresh(0, 0, y + 4, x + 2, y + h - 2, x + w - 2)

    window.refresh()
    return pad_text, extra_lines

def update_description(window, pad, app, current_resource):
    window.erase()
    window.box()

    window.addstr(2, 2, "Description of " + current_resource.get_name())
    window.refresh()
    h, w = window.getmaxyx()
    y, x = window.getbegyx()

    try:
        desc = app.describe(current_resource.get_type(), current_resource.get_name())
    except curses.error:
        desc = "Description not found"

    pad_text = desc
    temp = 0
    for i in desc.split("\n"):
        if len(i) > w:
            temp += len(i) // w
    extra_lines = temp

    pad.erase()
    pad.addstr(0, 0, desc)

    pad.refresh(0, 0, y + 4, x + 2, y + h - 2, x + w - 2)

    # window.refresh()
    return pad_text, extra_lines
