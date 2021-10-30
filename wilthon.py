import configparser
import inspect
import logging
import multiprocessing
import os
import threading
import psutil
import time
import winsound
import sys
import subprocess
from ctypes import windll, create_unicode_buffer
from shutil import copytree
from pynput import keyboard

# TODO MAYBE: ability to change max amount of backups before deletion
# env names: TEMP, APPDATA, ProgramFiles(x86)
BACKUP_DIR = os.path.expandvars(r"%APPDATA%\Wildlands Backup")


class Windows:
    @staticmethod
    def expand_path(foldervar, extra_path):
        return os.path.expandvars(fr"%{foldervar}%\{extra_path}")

    @staticmethod
    def expand_backup_path(extra_path):
        return os.path.expandvars(fr"%APPDATA%\Wildlands Backup\{extra_path}")

    @staticmethod
    def check_process(process_name):
        for proc in psutil.process_iter():
            try:
                if process_name.lower() in proc.name().lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    @staticmethod
    def find_executable_path(process_name):
        console_str = subprocess.check_output('tasklist', shell=True).decode("utf-8")
        console_list = list(filter(None, console_str.split("\r\n")))[2:]
        proc_list = list()
        for line in console_list:
            x = tuple(filter(None, line.split(" ")))[:-1]
            if len(x) == 5:
                proc_list.append(x)
        for name, pid, service_type, sessionno, memusage in proc_list:
            if name == process_name:
                pid_m = pid
        pid_match = psutil.Process(pid=pid_m)
        if pid_match.name() != "GRW.exe":
            return None
        return pid_match.exe()

    @staticmethod
    def amended_getcttime(file):
        return os.path.getmtime(os.path.expandvars(fr"%APPDATA%\Wildlands Backup\{file}"))

    @staticmethod
    def get_foreground_window_title():
        hWnd = windll.user32.GetForegroundWindow()
        length = windll.user32.GetWindowTextLengthW(hWnd)
        buf = create_unicode_buffer(length + 1)
        windll.user32.GetWindowTextW(hWnd, buf, length + 1)
        return buf.value if buf.value else None


# penis

class GameInstallation:
    is_ubisoft = None
    is_steam = None
    savegame_dir = ""
    unhandled_install_location = ""
    ubisoft_candidate_adress = ""
    steam_candidate_adress = ""
    ubisoft_count = 0
    steam_count = 0

    @staticmethod
    def install_dir_exception_handler():
        def message_producer(message):
            install_handler_input = Script.input_log(message)
            while not os.path.exists(install_handler_input) or (install_handler_input[
                                                                -4:] != "1771" and install_handler_input[
                                                                                   -4:] != "3559"):
                if not os.path.exists(install_handler_input):
                    logger.warning(
                        "The path you entered does not exist.")
                    time.sleep(0.05)
                    install_handler_input = Script.input_log(
                        message)
                elif not install_handler_input.endswith("1771") and not install_handler_input.endswith("3559"):
                    logger.warning(
                        "The path you entered is not a valid savegame directory.")
                    time.sleep(0.05)
                    install_handler_input = Script.input_log(
                        message)
            return install_handler_input

        def sub_set_savegame_as(version, set_to):
            if version.lower() == "steam":
                GameInstallation.is_steam = True
                GameInstallation.is_ubisoft = False
                GameInstallation.savegame_dir = set_to
            elif version.lower() == "ubisoft":
                GameInstallation.is_steam = False
                GameInstallation.is_ubisoft = True
                GameInstallation.savegame_dir = set_to
            else:
                raise Exception

        def meta_set_savegame_as(set_to):
            if set_to.endswith("3559"):
                sub_set_savegame_as("steam", set_to)
            if set_to.endswith("1771"):  # ubi
                sub_set_savegame_as("ubisoft", set_to)
            Options.savegame_dir = GameInstallation.savegame_dir

        if GameInstallation.ubisoft_count >= 2:
            logger.warning(
                r"Multiple savegame files for different Ubisoft installations of Ghost Recon: Wildlands found in C:\Program Files (x86).")
            time.sleep(0.05)
            multiple_ubisoft_found_input = message_producer("Enter the path to your preferred savegame folder.")
            meta_set_savegame_as(multiple_ubisoft_found_input)
            return
        if GameInstallation.steam_count >= 2:
            logger.warning(
                r"Multiple savegame files for different Steam installations of Ghost Recon: Wildlands found in C:\Program Files (x86).")
            time.sleep(0.05)
            multiple_steam_found_input = message_producer("Enter the path to your preferred savegame folder.")
            meta_set_savegame_as(multiple_steam_found_input)
            return
        if GameInstallation.is_ubisoft and GameInstallation.is_steam:
            logger.warning(
                r"Multiple savegame files for different installations of Ghost Recon: Wildlands found in C:\Program Files (x86).")
            time.sleep(0.05)
            multiple_versions_found_input = Script.input_guard(
                "Enter \"Steam\" to select the Steam version or enter \"Ubisoft\" to enter the Ubisoft version.",
                ("steam", "ubisoft"))
            if multiple_versions_found_input.lower() == "steam":
                sub_set_savegame_as("steam", GameInstallation.steam_candidate_adress)
            if multiple_versions_found_input.lower() == "ubisoft":
                sub_set_savegame_as("ubisoft", GameInstallation.ubisoft_candidate_adress)
            Options.savegame_dir = GameInstallation.savegame_dir
            return
        if GameInstallation.is_ubisoft is None and GameInstallation.is_steam is None:
            logger.error(r"No savegame files for Ghost Recon: Wildlands found in C:\Program Files (x86).")
            no_savegames_found_input = message_producer(
                "Enter the path to your savegames folder.")
            meta_set_savegame_as(no_savegames_found_input)

    @staticmethod
    def install_handler(*, called_recursively):  # maybe set returns as True/False?
        if not called_recursively:
            GameInstallation.unhandled_install_location = Windows.find_executable_path("GRW.exe")
        if GameInstallation.unhandled_install_location is None or GameInstallation.unhandled_install_location.lower() == "r":
            logger.error(
                "No running Ghost Recon: Wildlands iteration detected. An iteration of Ghost Recon: Wildlands needs to be running or the path to game executable must be given for setup to continue.")
            time.sleep(0.05)
            install_location_input = Script.input_log("R to retry, or input path to game executable.")
            if install_location_input.lower() == "r":
                GameInstallation.unhandled_install_location = Windows.find_executable_path("GRW.exe")
                GameInstallation.install_handler(called_recursively=True)
                return
            else:
                GameInstallation.unhandled_install_location = install_location_input
                GameInstallation.install_handler(called_recursively=True)
                return
        if not os.path.exists(GameInstallation.unhandled_install_location):
            logger.warning("Custom path does not seem to exist.")
            time.sleep(0.05)
            install_location_input = Script.input_log("R to retry, or input another custom path.")
            GameInstallation.unhandled_install_location = install_location_input
            GameInstallation.install_handler(called_recursively=True)
            return
        if not Options.executable_check(GameInstallation.unhandled_install_location):
            logger.warning("Path does not contain Ghost Recon: Wildlands executable.")
            time.sleep(0.05)
            install_location_input = Script.input_log("R to retry, or input another custom path.")
            GameInstallation.unhandled_install_location = install_location_input
            GameInstallation.install_handler(called_recursively=True)
            return
        Options.install_location = GameInstallation.unhandled_install_location


class Script:  # for meta stuff
    version = "0.1.1"

    @staticmethod
    def logger_initialize(init_stream_handler=True, init_file_handler=True):
        def fmt_filter(record):
            record.levelname = "[%s]" % record.levelname
            return True

        global logger, file_h
        if init_stream_handler:
            logger = logging.getLogger(__name__)
            logging.basicConfig(
                format='%(asctime)-22s %(levelname)-12s %(message)s',
                level=logging.INFO,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            logger.addFilter(fmt_filter)
        if init_file_handler:
            file_h_formatter = logging.Formatter('%(asctime)-22s %(levelname)-12s %(message)s', '%Y-%m-%d %H:%M:%S')
            file_h = logging.FileHandler(
                Windows.expand_backup_path(rf"""Logs\log{time.strftime("%Y-%m-%d %H.%M.%S")}.log"""))
            file_h.setFormatter(file_h_formatter)
            logger.addHandler(file_h)

    @staticmethod
    def install():
        Script.logger_initialize(init_stream_handler=False, init_file_handler=True)
        logger.info("Successfully created directory \"Wildlands Backup\".")
        logger.info("Successfully created directory \"Wildlands Backup\\Logs\".")
        GameInstallation.install_handler(called_recursively=False)
        for subdir in [x[0] for x in os.walk(Windows.expand_path("ProgramFiles(x86)",
                                                                 r'Ubisoft\Ubisoft Game Launcher\savegames'))]:  # for every subdir in SAVEGAME_SUPERDIR
            if subdir.endswith("1771"):  # ubi install
                GameInstallation.is_ubisoft = True
                GameInstallation.steam_candidate_adress = subdir
                logger.info("A Ubisoft Connect install of Ghost Recon: Wildlands detected.")
                GameInstallation.ubisoft_count += 1
            if subdir.endswith("3559"):  # steam install
                GameInstallation.is_steam = True
                GameInstallation.ubisoft_candidate_adress = subdir
                logger.info("A Steam install of Ghost Recon: Wildlands detected.")
                GameInstallation.steam_count += 1
        GameInstallation.install_dir_exception_handler()
        if GameInstallation.is_steam:
            Options.steam_question()
        Options.savegame_dir = GameInstallation.savegame_dir
        Options.interval_question()
        Options.index_question()
        Options.launch_on_launch_question()
        Options.write_to_ini()

    @staticmethod
    def input_log(message):
        def flash_window():
            while True:
                try:
                    while "cmd.exe" not in Windows.get_foreground_window_title():
                        windll.user32.FlashWindow(windll.kernel32.GetConsoleWindow(), True)
                        time.sleep(0.5)
                except TypeError:
                    time.sleep(0.1)
                else:
                    break

        t = threading.Thread(target=flash_window)
        # t.setDaemon(True)
        t.start()
        return input(f"""{time.strftime("%Y-%m-%d %H:%M:%S")}{"".ljust(4)}[INPUT]{"".ljust(6)}{message} """)

    @staticmethod
    def input_guard(message, expected_tuple=("y", "n", "yes", "no"), wrong_notif="Please enter a correct input:"):
        expected_display = list()
        for e in expected_tuple:
            expected_display.append(e)
            expected_display.append("/")
        expected_display.pop()
        expected_display = "".join(expected_display)
        wrong_notif += f' ({expected_display}'
        guarded_input = Script.input_log(f"{message} ({expected_display})")
        while guarded_input.lower() not in expected_tuple:
            logger.warning(wrong_notif)
            time.sleep(0.05)
            guarded_input = Script.input_log(message)
        return guarded_input.lower()

    @staticmethod
    def launch_game(install_type, steam_install_location, pause_exit_checks, first_launch=False):
        if first_launch:
            logger.info("No running instance of Ghost Recon: Wildlands detected, launching game...")
        else:
            logger.info("Relaunching Wildlands...")
        if install_type == "Steam":
            subprocess.call(r"Steam.exe -applaunch 460930", cwd=steam_install_location, shell=True)
        elif install_type == "Ubisoft":
            os.startfile(Options.install_location)
        while not Windows.check_process("GRW.exe"):
            time.sleep(1)
        logger.info("Pausing functionality for a grace period of 60 seconds.")
        time.sleep(60)
        pause_exit_checks.value = False


class Routine:

    @staticmethod
    def back_savegames_up(options_savegame_dir, options_backup_interval, suspend_event,
                          pause_exit_checks):  # pass data from __main__ as args
        Script.logger_initialize()
        while True:
            while suspend_event.value:
                time.sleep(0.2)
            while pause_exit_checks.value:
                time.sleep(0.2)
            new_backup_dirname = time.strftime("%Y-%m-%d %H.%M.%S")  # ISO 8601
            os.mkdir(Windows.expand_backup_path(f"{new_backup_dirname}"))
            copytree(options_savegame_dir, Windows.expand_backup_path(f"{new_backup_dirname}"),
                     dirs_exist_ok=True)  # destination
            logger.info("Successfully backed savegames up.")
            time.sleep(float(options_backup_interval))

    @staticmethod
    def delete_unneccesary_backups(suspend_event, pause_exit_checks):
        def convert_seconds(seconds):
            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)

            def zero_checker(var, time_type):
                if var == 0:
                    return "", ""
                else:
                    return f"""{int(var)} {time_type + "s" if var != 1 else time_type}""", " "

            h_string = zero_checker(h, "hour")
            m_string = zero_checker(m, "minute")
            s_string = zero_checker(s, "second")
            return f"""{h_string[0]}{h_string[1]}{m_string[0]}{m_string[1]}{s_string[0]}""".rstrip(" ")

        Script.logger_initialize()
        while True:
            while suspend_event.value:
                time.sleep(0.2)
            while pause_exit_checks.value:
                time.sleep(0.2)

            folder_count = 0
            for _, dirnames, filenames in os.walk(BACKUP_DIR):  # count folders
                folder_count += len(dirnames)
            if folder_count > 11:  # Include logs folder
                folder_list = os.listdir(BACKUP_DIR)
                for e in ["Logs", "options.ini"]:
                    folder_list.remove(e)
                oldest_folder = min(folder_list, key=Windows.amended_getcttime)
                oldest_folder_subs = os.listdir(Windows.expand_backup_path(oldest_folder))
                # oldest_folder_time = os.path.getmtime(Windows.expand_backup_path(oldest_folder))
                for file in oldest_folder_subs:
                    os.remove(Windows.expand_backup_path(fr"{oldest_folder}\{file}"))
                os.rmdir(Windows.expand_backup_path(oldest_folder))
                logger.info(
                    f"""Successfully removed oldest savegame.""")  # , which was backed up {convert_seconds(time.time() - oldest_folder_time)} ago.

    @staticmethod
    def handle_game_exits(options_index_to_restore, options_savegame_dir, options_steam_install_location,
                          options_install_type, first_passthrough, suspend_event,
                          exit_event, pause_exit_checks):
        Script.logger_initialize()

        def manual_restore(options_backup_interval, options_savegame_dir):
            Script.logger_initialize()
            while True:
                try:
                    manual_restore_input = int(Script.input_log(
                        "Which folder should be restored? Enter a cardinal number, e.g. 3 for third newest."))
                except ValueError:
                    logger.warning("Please enter a corrent number.")
                    time.sleep(0.05)
                else:
                    break
            manual_restore_confirmation_input = Script.input_guard(
                f"This equates to a roll back of {manual_restore_input * int(options_backup_interval) * 60} minutes, are you sure?")
            if manual_restore_confirmation_input.lower() == "y":
                newest_file_list = sorted(os.listdir(BACKUP_DIR), key=Windows.amended_getcttime)
                copytree(Windows.expand_backup_path(f"{newest_file_list[-1 * manual_restore_input]}"),
                         options_savegame_dir, dirs_exist_ok=True)
                logger.info("Successfully restored savegames.")
                return
            else:
                manual_restore(options_backup_interval, options_savegame_dir)
                return

        def restore_savegames(options_index_to_restore, options_savegame_dir):
            newest_file_list = sorted(os.listdir(BACKUP_DIR), key=Windows.amended_getcttime)
            copytree(Windows.expand_backup_path(f"{newest_file_list[-1 * int(options_index_to_restore)]}"),
                     options_savegame_dir, dirs_exist_ok=True)
            logger.info("Successfully restored savegames.")

        def exit_routine(exit_event):
            logger.info("Quitting script...")
            time.sleep(1)
            logging.shutdown()
            exit_event.value = True

        sys.stdin = open(
            0)  # omg why is this not the first thing that pops up when searching for EOFError, i spent like 5h on this crap
        while True:
            # while suspend_event.value: # do not suspend handle_game_exits as its supposed to be the handler of this
            #     time.sleep(0.2)

            if Windows.check_process("GRW.exe"):
                if first_passthrough:
                    first_passthrough = False
                time.sleep(1)
            elif first_passthrough:
                logger.info("Waiting for Ghost Recon: Wildlands to be running...")
                pause_exit_checks.value = True
                first_passthrough = False
                while not Windows.check_process("GRW.exe"):
                    time.sleep(0.5)
                logger.info("Wildlands iteration detected, pausing functionality for a grace period of 60 seconds.")
                time.sleep(60)
                pause_exit_checks.value = False
            else:
                suspend_event.value = True
                logger.warning("No running iteration of Ghost Recon: Wildlands detected. Initating backup options...")
                time.sleep(0.05)
                backup_options_input = Script.input_guard(
                    "Do you want to keep the utility running and relaunch game? Enter r to restore but not relaunch, enter m for manual restore, w for manual restore without relaunch.",
                    ("y", "n", "r", "m", "w"))
                if backup_options_input.lower() == "y":
                    restore_savegames(options_index_to_restore, options_savegame_dir)
                    Script.launch_game(options_install_type, options_steam_install_location, pause_exit_checks)
                    suspend_event.value = False
                elif backup_options_input.lower() == "n":
                    exit_routine(exit_event)
                elif backup_options_input.lower() == "r":
                    restore_savegames(options_index_to_restore, options_savegame_dir)
                    exit_routine(exit_event)
                elif backup_options_input.lower() == "w":
                    manual_restore(options_index_to_restore, options_savegame_dir)
                    exit_routine(exit_event)
                elif backup_options_input.lower() == "m":
                    manual_restore(options_index_to_restore, options_savegame_dir)
                    Script.launch_game(options_install_type, options_steam_install_location, pause_exit_checks)
                    suspend_event.value = False

    @staticmethod
    def keyboard_listener():
        Script.logger_initialize()

        def on_press(key):
            # while suspend_event.value:
            #     time.sleep(0.2)

            key_str = str(key).replace("'", "")
            if key_str == "\"" and Windows.get_foreground_window_title() == "Ghost Recon® Wildlands":
                winsound.Beep(750, 250)
                newest_file_epoch_time = os.path.getctime(
                    Windows.expand_backup_path(max(os.listdir(BACKUP_DIR), key=Windows.amended_getcttime)))
                time_difference = int(((time.time() - newest_file_epoch_time) / 60))
                if time_difference >= 1:
                    time_to_display = time_difference
                    if time_difference == 1:
                        time_unit = "minute"
                    else:
                        time_unit = "minutes"
                else:
                    time_to_display = int(time.time() - newest_file_epoch_time)
                    if time_to_display == 1:
                        time_unit = "second"
                    else:
                        time_unit = "seconds"
                logger.info(f"""Wilthon is still running. Last backup was {time_to_display} {time_unit} ago.""")

        def win32_event_filter(msg, data):
            if data.vkCode == 0xC0 and Windows.get_foreground_window_title() == "Ghost Recon® Wildlands":  # " key
                k_listener._suppress = True
            else:
                k_listener._suppress = False
            return True

        with keyboard.Listener(on_press=on_press, win32_event_filter=win32_event_filter, supress=False) as k_listener:
            k_listener.join()


class Options:  # for the ini
    install_location = None
    # is_tab2m_remap_on = None
    index_to_restore = None
    backup_interval = None
    savegame_dir = None
    launch_on_launch = None
    steam_install_location = None

    @staticmethod
    def executable_check(folder):
        for file in os.listdir(folder.rstrip(r"\GRW.exe")):
            if file == "GRW.exe":
                return True
        return False

    @staticmethod
    def remap_question():
        tab_input = Script.input_guard("Do you want to remap M to Tab to change the map key in-game?")
        if tab_input == "y":
            Options.is_tab2m_remap_on = True
            return
        else:
            Options.is_tab2m_remap_on = False
            return

    @staticmethod
    def index_question():  # TODO fix mentions of called recursively here
        while True:
            try:
                index_answer = int(Script.input_log(
                    "Which folder should be restored on auto-restore? Enter a cardinal number, e.g. 3 for third newest."))
            except ValueError:
                logger.warning("Please enter a corrent number.")
                time.sleep(0.05)
            else:
                break
        minutes_conf_message = int(index_answer * Options.backup_interval / 60)
        seconds_conf_message = int(index_answer * Options.backup_interval)
        if int(index_answer * Options.backup_interval / 60) > 0:
            confirmation_message = f"""This equates to the script autorestoring a savegame from {minutes_conf_message} {"minutes" if minutes_conf_message != 1 else "minute"} ago, are you sure?"""
        else:
            confirmation_message = f"""This equates to the script autorestoring a savegame from {seconds_conf_message} {"seconds" if seconds_conf_message != 1 else "second"} ago, are you sure?"""
        index_confirmation_input = Script.input_guard(confirmation_message)
        if index_confirmation_input == "y":
            Options.index_to_restore = index_answer
            return
        else:
            Options.index_question()
            return

    @staticmethod
    def interval_question(*, seconds_mode=False):
        if seconds_mode:
            interval_answer = Script.input_log(
                "How often should backups be made? (in seconds, enter \"m\" to switch to minutes.)")
        else:
            interval_answer = Script.input_log(
                "How often should backups be made? (in minutes, enter \"s\" to switch to seconds.)")
        if interval_answer.isnumeric():
            if seconds_mode:
                Options.backup_interval = float(interval_answer)
            else:
                Options.backup_interval = float(interval_answer) * 60
        elif interval_answer == "s" and not seconds_mode:
            Options.interval_question(seconds_mode=True)
            return
        elif interval_answer == "m" and seconds_mode:
            Options.interval_question(seconds_mode=False)
            return
        else:
            logger.warning("Please enter a valid input.")
            time.sleep(0.05)
            Options.interval_question(seconds_mode=seconds_mode)
            return

    @staticmethod
    def steam_question(recursive_input=None):
        if recursive_input is not None:
            unhandled_install_location = Windows.find_executable_path("Steam.exe")
        else:
            unhandled_install_location = recursive_input
        if unhandled_install_location is None:  # or unhandled_install_location.lower() == "r"
            logger.error(
                "No running Steam iteration detected. An iteration of Steam needs to be running or the path to Steam executable must be given for setup to continue.")
            time.sleep(0.05)
            install_location_input = Script.input_log("R to retry, or input path to game executable.")
            if install_location_input.lower() == "r":
                unhandled_install_location = Windows.find_executable_path("Steam.exe")
                Options.steam_question(unhandled_install_location)
                return
            else:
                unhandled_install_location = install_location_input
                Options.steam_question(unhandled_install_location)
                return
        if not os.path.exists(unhandled_install_location):
            logger.warning("Custom path does not seem to exist.")
            time.sleep(0.05)
            install_location_input = Script.input_log("R to retry, or input another custom path.")
            unhandled_install_location = install_location_input
            Options.steam_question(unhandled_install_location)
            return
        for file in os.listdir(unhandled_install_location.rstrip(r"\Steam.exe")):
            if file == "Steam.exe":
                executable_check = True
            else:
                executable_check = False
        if not executable_check:
            logger.warning("Path does not contain Steam executable.")
            time.sleep(0.05)
            install_location_input = Script.input_log("R to retry, or input another custom path.")
            unhandled_install_location = install_location_input
            Options.steam_question(unhandled_install_location)
            return
        Options.steam_install_location = unhandled_install_location

    @staticmethod
    def launch_on_launch_question():
        launch_input = Script.input_guard(
            "Would you like Wilthon to automatically launch Ghost Recon: Wildlands if it isn't running already on launch?")
        if launch_input == "y":
            Options.launch_on_launch = True
        else:
            Options.launch_on_launch = False

    @staticmethod
    def initialize():
        config = configparser.ConfigParser()
        config.read(Windows.expand_backup_path("options.ini"))
        attributes = inspect.getmembers(Options, lambda a: not (inspect.isroutine(a)))
        for e in [a for a in attributes if not (a[0].startswith('__') and a[0].endswith('__'))]:
            setattr(Options, e[0], config["Options"][e[0]])
        if Options.savegame_dir.endswith("3559"):
            Options.install_type = "Steam"
        else:
            Options.install_type = "Ubisoft"

    @staticmethod
    def write_to_ini():
        config = configparser.ConfigParser()
        if os.path.isfile(Windows.expand_backup_path("options.ini")):
            config.read(Windows.expand_backup_path("options.ini"))
        else:
            open(Windows.expand_backup_path("options.ini"), 'a').close()  # create ini
            config.read(Windows.expand_backup_path("options.ini"))
            config["Options"] = {}
        attributes = inspect.getmembers(Options, lambda a: not (inspect.isroutine(a)))
        for e in [a for a in attributes if not (a[0].startswith('__') and a[0].endswith('__'))]:
            config["Options"][e[0]] = str(getattr(Options, e[0]))
        with open(Windows.expand_backup_path("options.ini"), 'w') as configfile:  # save
            config.write(configfile)


if __name__ == "__main__":  # init
    Script.logger_initialize(init_stream_handler=True, init_file_handler=False)
    if os.path.isdir(BACKUP_DIR):
        Options.initialize()
    else:
        logger.info("No prior installation of Wilthon detected. Initiating installation...")
        Script.install()

    processes = []
    num_processes = os.cpu_count()

    suspend_event = multiprocessing.Value("i", False)
    exit_event = multiprocessing.Value("i", False)
    pause_exit_checks = multiprocessing.Value("i", False)
    if Options.launch_on_launch and not Windows.check_process("GRW.exe"):
        Script.launch_game(Options.install_type, Options.steam_install_location, pause_exit_checks, first_launch=True)
    first_passthrough = True
    p1 = multiprocessing.Process(target=Routine.back_savegames_up, args=(
        Options.savegame_dir, Options.backup_interval, suspend_event, pause_exit_checks))
    p2 = multiprocessing.Process(target=Routine.delete_unneccesary_backups,
                                 args=(suspend_event, pause_exit_checks))
    p3 = multiprocessing.Process(target=Routine.handle_game_exits, args=(
        Options.index_to_restore, Options.savegame_dir, Options.steam_install_location, Options.install_type,
        first_passthrough, suspend_event, exit_event,
        pause_exit_checks))
    p4 = multiprocessing.Process(target=Routine.keyboard_listener)

    processes.append(p1)
    processes.append(p2)
    processes.append(p4)
    processes.append(p3)

    for process in processes:
        process.start()
        print(process.name + "->" + str(process.pid))

    while True:
        if exit_event.value:
            for process in processes:
                process.terminate()
            break
