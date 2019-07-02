import sys, os # TODO is this ok
import curses
import json
import copy
from pyfiglet import Figlet
from resource import Resource
import helpers
from requests.packages import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# import inspect
# import subprocess
# import textwrap
# from time import sleep

sys.path.insert(0, '../backend/')
# sys.path.insert(0, '../../../Collector/skipper-collector/') # TODO WARNING this only works on my computer
import app_hierarchy
import cluster_mode_backend as cluster_hierarchy
import k8s_config
# cluster_functions = inspect.getmembers(cluster_hierarchy, inspect.isfunction)

# app_resources = {}
# app_relations = {}
# infra_resources_relations = {}
app_objects = {}
cluster_jsons = {}

command = "kubectl get applications"
app_lines = app_hierarchy.load(command).split('\n')[1:-1]
for line in app_lines:
    name = line.split()[0]
    app_objects[name] = app_hierarchy.Application(name, hierarchy_only=False, test_printing=False)

skipper_figlet_lines = Figlet(font="standard").renderText("skipper").split("\n")

stdscr, app_jsons = helpers.initialize(app_objects, skipper_figlet_lines)

# with open('resources_hierarchy-only_modified.json') as json_file:
#     app_resources['gbapp-gbapp'] = json.load(json_file)
# with open('relations_hierarchy-only.json') as json_file:
#     app_relations['gbapp-gbapp'] = json.load(json_file)
# with open('infra_local-cluster_modified.json') as json_file:
#     infra_resources_relations['local_cluster'] = json.load(json_file)
# with open('app:boisterous-shark-gbapp.json') as json_file:
#     app_jsons[app_name] = json.load(json_file)

def get_children(current_resource, mode, app_name="", cluster=""): # TODO update the docstring!!!
    """
    :param current_resource: a Resource object
    :return: list of resources that have current_resource as a parent
    """
    if mode == 'app':
        hierarchy = app_jsons[app_name]['Relations']
    # elif mode == 'infra':
    #     hierarchy = infra_resources_relations['local_cluster']['Relations']
    elif mode == 'cluster':
        hierarchy = cluster_jsons[cluster]
    children = []
    for relation_type in hierarchy.keys():
        if relation_type.split("<-")[0] == current_resource.get_type():
            # print(type(current_resource))
            for pair in hierarchy[relation_type]:
                name = current_resource.get_name()
                if pair[0] == name:
                    children.append(Resource(pair[1], relation_type.split("<-")[1]))
    return children

def get_parent_menu(current_path, current_type_path, mode, app_name, cluster): # TODO update the docstring!!!
    """
    :param current_resource: a Resource object
    :return: (list of resources that include parent of current_resource and siblings of that parent, index of parent)
    """

    path_components = current_path.split("/")
    if len(path_components) > 3:
        grandparent = Resource(path_components[-3], current_type_path.split("/")[-3])
        parent = Resource(path_components[-2], current_type_path.split("/")[-2])
        parent_menu = get_children(grandparent, mode, cluster=cluster, app_name=app_name)
        resource = parent
        path = '/'.join(current_path.split("/")[:-2] + [""])
        type_path = '/'.join(current_type_path.split("/")[:-2]+[""])
    else:
        path = '/'
        type_path = '/'
        if mode == 'app':
            parent_menu = [Resource(app_name, 'Application') for app_name in app_objects.keys()]
            resource = Resource(app_name, 'Application')
        elif mode == 'cluster':
            parent_menu = get_cluster_menu()
            resource = Resource(cluster, 'Cluster')

    for res in parent_menu:
        if res == resource:
            parent_index = parent_menu.index(res)

    return (parent_menu, parent_index, path, type_path)

def get_cluster_menu():
    k8s_config.update_available_clusters()
    clusters = k8s_config.all_cluster_names()
    menu = [Resource(c, 'Cluster') for c in clusters]
    return menu

# # for use when there isn't a json for the cluster, and must go through methods to get all children
# def get_cluster_children(cluster, namespace, current_resource):
#     children = []
#     if current_resource.get_type() == 'Cluster':
#         names = cluster_hierarchy.cluster_namespaces(current_resource.get_name())
#         children = [Resource(ns, 'Namespace') for ns in names]
#         cluster = current_resource.get_name()
#     else:
#         valid_functions = [fn for fn in cluster_functions if fn[0].split("_")[0] == current_resource.get_type().lower()
#                                                             and len(fn[0].split("_")) == 3]
#         for fn in valid_functions:
#             type = fn[0].split("_")[1].capitalize()
#             if current_resource.get_type() == 'Namespace':
#                 namespace = current_resource.get_name()
#                 names = fn[1](current_resource.get_name(),cluster)
#                 children = children + [Resource(name, type) for name in names]
#             else:
#                 names = fn[1](current_resource.get_name(), namespace, cluster)
#                 children = children + [Resource(name, type) for name in names]
#     return children, namespace, cluster

def menu_main(menu_window, info_window, menu, path, type_path):

    def print_menu(window, menu_to_print, selected_row_idx, name_path, type_path, mode):
        window.erase()
        window.attron(curses.color_pair(6))
        window.addstr(0, 0, "> " + mode + " mode")
        window.attroff(curses.color_pair(6))
        window.addstr(2, 0, name_path)
        type_path_format = format_type_path(type_path, name_path)
        add_string_by_color(type_path_format, window, 3, 0)
        h, w = window.getmaxyx()
        for idx, row in enumerate(menu_to_print):
            x = w // 2 - len(row) // 2
            y = h // 2 - len(menu_to_print) // 2 + idx
            if idx == selected_row_idx:
                strings = row.split(" ")
                string_info = [(strings[0]+" ",curses.color_pair(8)),(strings[1],curses.color_pair(1))]
                add_string_by_color(string_info,window,idx+5,0)
                # window.attron(curses.color_pair(1))
                # window.addstr(idx+3, 0, row)
                # window.attroff(curses.color_pair(1))
            else:
                strings = row.split(" ")
                string_info = [(strings[0]+" ", curses.color_pair(6)), (strings[1], curses.color_pair(9))]
                add_string_by_color(string_info, window, idx + 5, 0)
                # window.addstr(idx+3, 0, row)
        window.refresh()

    def format_type_path(type_path, name_path):
        string_info = [(" ",curses.color_pair(0))]
        for i, name in enumerate(name_path.split("/")):
            if len(name) == 0:
                continue
            string_info.append((helpers.get_abbrv(type_path.split("/")[i]).center(len(name)," ") + " ",
                                curses.color_pair(6)))
        return string_info

    def add_string_by_color(string_info, window, start_y, start_x):
        current_x = start_x
        for text, color in string_info:
            window.attron(color)
            try:
                window.addstr(start_y, current_x, text)
            except:
                break # TODO handle this!
            window.attroff(color)
            current_x += len(text)
        return

    menu_window.attron(curses.color_pair(1))
    h, w = menu_window.getmaxyx()

    # initial settings
    current_row = 0
    current_resource = menu[current_row]
    current_path = path
    current_type_path = type_path
    switch_mode = False
    app = app_objects[current_resource.get_name()]
    app_name = current_resource.get_name()
    mode = 'app'
    info_type = 'D'
    cluster = ''

    # create pad for displaying info in right/info window. TODO formatting issues
    y, x = info_window.getbegyx()
    info_pad = curses.newpad(55, w - 4)  # theoretically, h-6 for height?
    info_pad.box()
    info_pad.scrollok(True)
    # info_pad.setscrreg(0,pad_h-1)
    info_pad_pos = 0
    pad_text = ""
    extra_lines = 0

    # print the menu
    menu_to_print = [str(resource) for resource in menu]
    print_menu(menu_window, menu_to_print, current_row, current_path, current_type_path, mode)

    key = 0

    while (key != ord('q')):

        # keys to navigate up, down, left, right
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(menu) - 1:
            current_row += 1
        elif key == curses.KEY_RIGHT:
            # first time getting cluster info
            if current_resource.get_type() == 'Cluster' and current_resource.get_name() not in cluster_jsons.keys():
                cluster_jsons[current_resource.get_name()] = cluster_hierarchy.cluster_as_json(current_resource.get_name())

            menu_temp = get_children(current_resource, mode, cluster=cluster, app_name=app_name)
            if len(menu_temp) > 0: # 1+ children
                current_path = current_path + current_resource.get_name() + '/'
                current_type_path = current_type_path + current_resource.get_type() + '/'
                menu = copy.deepcopy(menu_temp)
                current_row = 0
        elif key == curses.KEY_LEFT:
            menu, current_row, current_path, current_type_path = get_parent_menu(current_path,current_type_path,mode, app_name, cluster)

        # keys to switch modes
        # TODO handle mode switching accurately, currently just jumps to top of hierarchy
        elif key == ord('1'):
            mode = 'cluster'
            menu = get_cluster_menu()
            current_row = 0
            cluster = menu[current_row].get_name() # TODO handle empty menu
            current_path = "/"
            current_type_path = "/"
        elif key == ord('2'): #and switch_mode:
            # TODO
            # question: do we allow switching when the resource doesn't exactly correspond?
            # e.g. if on a deployable and try to switch to cluster mode, does nothing happen, or do we go to top of cluster hierarchy?
            mode = 'app'
            menu = [Resource(app, 'Application') for app in app_objects.keys()]
            current_row = 0
            app_name = menu[current_row].get_name()
            app = app_objects[app_name]
            current_path = "/"
            current_type_path = "/"
        elif key == ord('3'): # TODO is this the right place handle this input? seems like it should be in main
            pass
        elif key == ord('4'): # TODO
            pass

        # keys for displaying different resource info
        elif key == ord('Y'):
            info_type = 'Y'
            pad_text, extra_lines = helpers.update_yaml(info_window, info_pad, app, current_resource)
        elif key == ord('L'):
            info_type = 'L'
            pad_text, extra_lines = helpers.update_logs(info_window, info_pad, app, current_resource)
        elif key == ord('E'):
            info_type = 'E'
            # TODO get k8s events
        elif key == ord('D'):
            info_type = 'D'
            pad_text, extra_lines = helpers.update_description(info_window, info_pad, app, current_resource)

        # keys for scrolling
        # TODO can change these keys, they were pretty arbitrary
        elif key == ord('w'):
            # info_pad.scroll(-10)
            if info_pad_pos > 0:
                info_pad_pos -= 1
                # info_pad.clear()
                info_pad.refresh(info_pad_pos, 0, y + 4, x + 2, y + h -2 + 4, x + w - 2)
            # cursy, cursx = info_pad.getyx()
        elif key == ord('s'):
            # info_pad.scroll(10)
            if (info_pad_pos <= len(pad_text.split("\n")) + extra_lines - (h - 6)
                    and len(pad_text.split("\n")) + extra_lines > (h-6)): # TODO think about logic
                info_pad_pos += 1
                # info_pad.clear()
                info_pad.refresh(info_pad_pos, 0, y + 4, x + 2, y + h - 2 + 4, x + w - 2)
            # cursy, cursx = info_pad.getyx()

        menu_to_print = [str(resource) for resource in menu]
        current_resource = menu[current_row]
        print_menu(menu_window, menu_to_print, current_row, current_path, current_type_path, mode)

        # can switch between app and infra mode on pod
        # TODO edit for cluster mode
        if current_resource.get_type() == "Pod" and current_resource.get_name() in app_jsons[app_name]["Resources"]["Pod"]:
            switch_mode = True
        else:
            switch_mode = False

        # keep track of highest level resource
        # honestly don't quite remember what issue caused me to add this, but not confident it works without it
        if current_resource.get_type() == 'Application':
            app_name = current_resource.get_name()
            app = app_objects[app_name]
        if current_resource.get_type() == 'Cluster':
            cluster = current_resource.get_name()

        # update info panel to reflect current selected resource
        if info_type == 'Y' and key not in [ord('w'),ord('s')]:
            pad_text, extra_lines = helpers.update_yaml(info_window, info_pad, app, current_resource)
        elif info_type == 'L' and key not in [ord('w'),ord('s')]:
            pad_text, extra_lines = helpers.update_logs(info_window, info_pad, app, current_resource)
        elif info_type == 'D' and key not in [ord('w'),ord('s')]:
            pad_text, extra_lines = helpers.update_description(info_window, info_pad, app, current_resource)

        key = stdscr.getch()

    # terminate()
    return 0

def run_skipper(stdscr):

    c = 0
    cursor_x = 0
    cursor_y = 0

    # stdscr.nodelay() # TODO double check this

    stdscr.erase()
    # stdscr.clear()
    # stdscr.refresh()

    # Start colors in curses
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_RED, -1) # example of pair of foreground/bg color, -1 is default
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)
    curses.init_pair(5, curses.COLOR_BLUE, -1)
    curses.init_pair(6, curses.COLOR_MAGENTA, -1)
    curses.init_pair(7, curses.COLOR_CYAN, -1)
    curses.init_pair(8, curses.COLOR_MAGENTA, curses.COLOR_WHITE)
    curses.init_pair(9, curses.COLOR_WHITE, -1)

    height, width = stdscr.getmaxyx()

    # Strings for top panel
    resource_key_binds = "resource key binds"
    keybinds_basic = ['[esc] command mode', '[shift-l] left pane', '[shift-r] right pane', '[shift-b] back', '[q] quit']
    keybinds_mode = ['[1] cluster mode', '[2] app mode', '[3] anomaly mode', '[4] query mode']
    keybinds_resource = ['[shift-s] summary', '[shift-d] describe', '[shift-y] yaml', '[shift-l] logs', '[shift-e] k8s events']

    # Important coordinates
    col_space = 5
    line_space = 1
    skipper_figlet_offset_x = col_space
    skipper_figlet_offset_y = line_space
    bindings_start_x = max(len(line) for line in skipper_figlet_lines) + col_space * 4
    bindings_start_y = line_space + 1

    # Loop where c is the last character pressed
    while (c != ord('q')):

        helpers.loading(stdscr,skipper_figlet_lines)

        ##################
        ### TOP WINDOW ###
        ##################

        top_window = helpers.create_window(len(skipper_figlet_lines)+line_space*2, width, 0, 0)
        top_window_height, top_window_width = top_window.getmaxyx()
        top_window.border(0,0,0,0,0,0,0,0)
        # top_window.box()

        # paint figlet
        y_temp = skipper_figlet_offset_y
        for line in skipper_figlet_lines:
            top_window.addstr(y_temp, skipper_figlet_offset_x, line) # TODO: how to catch if it goes outside window?
            y_temp += 1

        # paint all keybinds
        y_temp = bindings_start_y
        x_temp = bindings_start_x
        for kb in keybinds_basic:
            top_window.addstr(y_temp, x_temp, kb)  # TODO: how to catch if it goes outside window?
            y_temp += 1

        # reset y and increase x (move to right)
        y_temp = bindings_start_y
        x_temp += max(len(kb) for kb in keybinds_basic) + col_space
        for kb in keybinds_mode:
            top_window.addstr(y_temp, x_temp, kb)  # TODO: how to catch if it goes outside window?
            y_temp += 1

        x_temp += max(len(kb) for kb in keybinds_mode) + col_space*2
        top_window.addstr(bindings_start_y,x_temp, resource_key_binds)

        y_temp = bindings_start_y
        x_temp += len(resource_key_binds) + col_space
        for kb in keybinds_resource:
            top_window.addstr(y_temp, x_temp, kb)  # TODO: how to catch if it goes outside window?
            y_temp += 1

        top_window.refresh()

        ###################
        ### LEFT WINDOW ###
        ###################

        left_window = helpers.create_window(height-top_window_height, width//2, top_window_height, 0)
        left_window.border(0, 0, 0, 0, 0, 0, 0, 0)
        left_window_height, left_window_width = left_window.getmaxyx()

        left_window.refresh()

        ####################
        ### RIGHT WINDOW ###
        ####################

        right_window = helpers.create_window(height - top_window_height, width // 2, top_window_height, width // 2)
        right_window.border(0, 0, 0, 0, 0, 0, 0, 0)

        right_window.refresh()

        ############
        ### MENU ###
        ############

        # this is the menu window/panel for hierarchy navigation
        # window/panel is within left window
        menu_window, menu_panel = helpers.create_panel_in_window(2, 2, left_window)
        curses.panel.update_panels()
        stdscr.refresh()

        menu = [Resource(app, 'Application') for app in app_objects.keys()]
        exit_code = menu_main(menu_window, right_window, menu, "/", "/")

        if exit_code == 0:
            c = ord('q')

        #####################
        ### PROCESS INPUT ###
        #####################

        if c == 27: # TODO check
            pass
        elif c == 'L':
            pass
        elif c == 'R':
            pass
        elif c == 'B':
            pass
        elif c == '1':
            pass
        elif c == '2':
            pass
        elif c == '3':
            pass
        elif c == 'D':
            pass
        elif c == 'Y':
            pass
        elif c == 'L':
            pass
        elif c == 'E':
            pass
        elif c == ord('q'): # quit
            break

        # Refresh the screen
        stdscr.refresh()

        # Wait for next input
        c = stdscr.getch()

def main():
    curses.wrapper(run_skipper)

if __name__ == "__main__":
    main()


# # example of what you can do with panels
# for i in range(20):
#     panel1.move(8, 8 + i)
#     curses.panel.update_panels();
#     sleep(.1)
#     stdscr.refresh()
