import configparser
import ctypes
import logging
import os
import psutil
import subprocess
import time
import winsound
import sys
from ctypes import windll, create_unicode_buffer
from distutils.dir_util import copy_tree as copy_dir
from multiprocessing import Process
from pynput import keyboard

# TODO: consider adding advanced customasibility like changing remap keys, max amount of backups before deletion, add date to successfully removed oldest savegame
# TODO: test if remap and " work in game, ingame test
# env names: TEMP, APPDATA, ProgramFiles(x86)
SAVEGAME_SUPERDIR = r'Ubisoft\Ubisoft Game Launcher\savegames'
BACKUP_DIR = os.path.expandvars(r"%APPDATA%\Wildlands Backup")
NATIVES = ["Logs", "options.ini"]


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
    def find_executable_path(executable):
        pid = None
        for proc in psutil.process_iter():
            if executable in proc.name():
                pid = proc.pid
                break
        pid_match = psutil.Process(pid=pid)
        if pid_match.name() != "grw.exe":
            return None
        return pid_match.exe()

    @staticmethod
    def amended_getcttime(file):
        return os.path.getctime(os.path.expandvars(fr"%APPDATA%\Wildlands Backup\{file}"))

    @staticmethod
    def getForegroundWindowTitle():
        hWnd = windll.user32.GetForegroundWindow()
        length = windll.user32.GetWindowTextLengthW(hWnd)
        buf = create_unicode_buffer(length + 1)
        windll.user32.GetWindowTextW(hWnd, buf, length + 1)
        return buf.value if buf.value else None


class GameInstallation:
    # penis
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
                elif install_handler_input[-4:] != "1771" and install_handler_input[-4:] != "3559":
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
            if set_to[-4:] == "3559":  # steam
                sub_set_savegame_as("steam", set_to)
            if set_to[-4:] == "1771":  # ubi
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
            multiple_versions_found_input = Script.input_log(
                "Enter \"Steam\" to select the Steam version or enter \"Ubisoft\" to enter the Ubisoft version.")
            while multiple_versions_found_input.lower() != "steam" and multiple_versions_found_input.lower() != "ubisoft":
                logger.warning("Please enter a valid input: (Steam/Ubisoft)")
                time.sleep(0.05)
                multiple_versions_found_input = Script.input_log(
                    "Enter \"Steam\" to select the Steam version or enter \"Ubisoft\" to enter the Ubisoft version.")
            if multiple_versions_found_input.lower() == "steam":
                sub_set_savegame_as("steam", GameInstallation.steam_candidate_adress)
            if multiple_versions_found_input.lower() == "ubisoft":
                sub_set_savegame_as("ubisoft", GameInstallation.ubisoft_candidate_adress)
            Options.savegame_dir = GameInstallation.savegame_dir
            return
        if GameInstallation.is_ubisoft is None and GameInstallation.is_steam is None:
            logger.warning(r"No savegame files for Ghost Recon: Wildlands found in C:\Program Files (x86).")
            no_savegames_found_input = message_producer(
                "Enter the path to your savegame folder.")
            meta_set_savegame_as(no_savegames_found_input)

    @staticmethod
    def install_handler(*, called_recursively):  # maybe set returns as True/False?
        if not called_recursively:
            GameInstallation.unhandled_install_location = Windows.find_executable_path("grw.exe")
        if GameInstallation.unhandled_install_location is None or GameInstallation.unhandled_install_location.lower() == "r":
            logger.warning(
                "No running Ghost Recon: Wildlands iteration detected. An iteration of Ghost Recon: Wildlands needs to be running or the path to game executable must be given for setup to continue.")
            time.sleep(0.05)
            install_location_input = Script.input_log("R to retry, or input path to game executable.")
            if install_location_input.lower() == "r":
                GameInstallation.unhandled_install_location = Windows.find_executable_path("grw.exe")
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
    version = "0.1.0"
    pid_list = []

    @staticmethod
    def logger_initialize(*, is_install):
        def fmt_filter(record):
            record.levelname = "[%s]" % record.levelname
            return True

        if is_install:
            os.mkdir(Windows.expand_path("APPDATA", "Wildlands Backup"))
            os.mkdir(Windows.expand_backup_path("Logs"))
        global logger, file_h
        logger = logging.getLogger(__name__)
        logging.basicConfig(
            format='%(asctime)-22s %(levelname)-12s %(message)s',
            level=logging.INFO,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_h_formatter = logging.Formatter('%(asctime)-22s %(levelname)-12s %(message)s', '%Y-%m-%d %H:%M:%S')
        logger.addFilter(fmt_filter)
        file_h = logging.FileHandler(
            Windows.expand_backup_path(rf"""Logs\log{time.strftime("%Y-%m-%d %H.%M:%S")}.log"""))
        file_h.setFormatter(file_h_formatter)
        logger.addHandler(file_h)

    @staticmethod
    def updater():  # parse local version to be compared with remote version
        pass  # TODO: add updater, https://fernandofreitasalves.com/how-to-create-python-exe-with-msi-installer-and-cx_freeze/

    @staticmethod
    def install():
        # <editor-fold desc="">
        logger.info("Successfully created directory \"Wildlands Backup\".")
        logger.info("Successfully created directory \"Wildlands Backup\\Logs\".")
        # </editor-fold>
        GameInstallation.install_handler(called_recursively=False)
        for subdir in [x[0] for x in os.walk(Windows.expand_path("ProgramFiles(x86)",
                                                                 SAVEGAME_SUPERDIR))]:  # for every subdir in SAVEGAME_SUPERDIR
            if subdir[-4:] == "1771":  # ubi install
                GameInstallation.is_ubisoft = True
                GameInstallation.steam_candidate_adress = subdir
                logger.info("A Ubisoft Connect install of Ghost Recon: Wildlands detected.")
                GameInstallation.ubisoft_count += 1
            if subdir[-4:] == "3559":  # steam install
                GameInstallation.is_steam = True
                GameInstallation.ubisoft_candidate_adress = subdir
                logger.info("A Steam install of Ghost Recon: Wildlands detected.")
                GameInstallation.steam_count += 1
        GameInstallation.install_dir_exception_handler()
        Options.savegame_dir = GameInstallation.savegame_dir
        Options.interval_question()
        Options.index_question()
        Options.remap_question()
        Options.write_to_ini()

    @staticmethod
    def add_pid(pid):
        Script.pid_list.append(pid)

    @staticmethod
    def suspend_process(pid_list):
        # pid_list.remove(multiprocessing.current_process().pid), the pid of currently running process is never passed in because it is executed last
        for e in pid_list:
            psutil.Process(e).suspend()

    @staticmethod
    def unsuspend_process(pid_list):
        for e in pid_list:
            psutil.Process(e).resume()

    @staticmethod
    def kill_all_processes(pid_list):  # maybe implement cleaner with Process.terminate rather than 3rd party killing
        for e in pid_list:
            psutil.Process(e).kill()

    @staticmethod
    def input_log(message):
        ctypes.windll.user32.FlashWindow(ctypes.windll.kernel32.GetConsoleWindow(), True)
        return input(f"""{time.strftime("%Y-%m-%d %H:%M:%S")}{"".ljust(4)}[INPUT]{"".ljust(6)}{message} """)


class Routine:

    @staticmethod
    def initialize():
        open(Windows.expand_path("TEMP", "first_passthrough_flag.flag"), 'a').close()

    @staticmethod
    def back_savegames_up(options_savegame_dir, options_backup_interval):  # pass data from __main__ as args
        Script.logger_initialize(is_install=False)
        while True:
            new_backup_dirname = time.strftime("%Y-%m-%d %H.%M.%S")  # ISO 8601
            os.mkdir(Windows.expand_backup_path(f"{new_backup_dirname}"))
            copy_dir(options_savegame_dir, Windows.expand_backup_path(f"{new_backup_dirname}"))  # destination
            logger.info("Successfully backed savegame up.")
            time.sleep(float(options_backup_interval))

    @staticmethod
    def delete_unneccesary_backups():
        def convert_seconds(seconds):
            h = seconds // (60 * 60)
            m = (seconds - h * 60 * 60) // 60
            s = seconds - (h * 60 * 60) - (m * 60)

            def zero_checker(var, time_type):
                if var == 0:
                    return ""
                else:
                    return f"""{var} {time_type + "s" if var != 1 else time_type}"""

            h_string = zero_checker(h, "hour")
            m_string = zero_checker(m, "minute")
            s_string = zero_checker(s, "second")
            return f"""{h_string}{" " if h_string != "" else ""}{m_string}{" " if m_string != "" else ""}{s_string}"""

        Script.logger_initialize(is_install=False)
        while True:
            folder_count = 0
            for _, dirnames, filenames in os.walk(BACKUP_DIR):  # count folders
                folder_count += len(dirnames)
            if folder_count > 11:  # Include logs folder
                folder_list = os.listdir(BACKUP_DIR)
                for e in NATIVES:
                    folder_list.remove(e)
                oldest_folder = min(folder_list, key=Windows.amended_getcttime)
                oldest_folder_subs = os.listdir(Windows.expand_backup_path(oldest_folder))
                for file in oldest_folder_subs:
                    os.remove(Windows.expand_backup_path(fr"{oldest_folder}\{file}"))
                os.rmdir(Windows.expand_backup_path(oldest_folder))
                logger.info(
                    f"""Successfully removed oldest savegame, which was backed up {convert_seconds(int(time.time() - os.path.getctime(oldest_folder))).rstrip(" ")} ago.""")

    @staticmethod
    def handle_game_exits(pid_list, options_index_to_restore, options_savegame_dir, gameinstallation_is_steam,
                          gameinstallation_is_ubisoft, options_install_location):
        Script.logger_initialize(is_install=False)

        def manual_restore(options_backup_interval, options_savegame_dir):
            Script.logger_initialize(is_install=False)
            while True:
                try:
                    manual_restore_input = int(Script.input_log(
                        "Which folder should be restored? Enter a cardinal number, e.g. 3 for third newest."))
                except ValueError:
                    logger.warning("Please enter a corrent number.")
                    time.sleep(0.05)
                else:
                    break
            ynwatcher = Script.input_log(
                f"This equates to a roll back of {manual_restore_input * options_backup_interval * 60} minutes, are you sure? (y/n)")
            while ynwatcher.lower() != "y" and ynwatcher.lower() != "n":
                logger.warning("Please enter a correct input: (y/n)")
            if ynwatcher.lower() == "y":
                newest_file_list = sorted(os.listdir(BACKUP_DIR), key=Windows.amended_getcttime)
                copy_dir(Windows.expand_backup_path(f"{newest_file_list[-1 * manual_restore_input]}"),
                         options_savegame_dir)
                logger.info("Successfully restored savegames.")
                return
            else:
                manual_restore(options_backup_interval, options_savegame_dir)
                return

        def relaunch(gameinstallation_is_ubisoft, gameinstallation_is_steam, options_install_location):
            # Script.logger_initialize(is_install=False)
            logger.info("Relaunching Ghost Recon: Wildlands...")
            if gameinstallation_is_ubisoft:
                os.startfile(options_install_location)  # os.spawnl(os.P_NOWAIT, Options.install_location, "")
            if gameinstallation_is_steam:
                subprocess.call("steam://rungame/id/460930")

        def restore_savegames(options_index_to_restore, options_savegame_dir):
            # Script.logger_initialize(is_install=False)
            newest_file_list = sorted(os.listdir(BACKUP_DIR), key=Windows.amended_getcttime)
            copy_dir(Windows.expand_backup_path(f"{newest_file_list[-1 * options_index_to_restore]}"),
                     options_savegame_dir)
            logger.info("Successfully restored savegames.")

        def exit_routine(pid_list):
            logger.info("Quitting script...")
            Script.kill_all_processes(pid_list)
            logging.shutdown()
            exit(0)

        first_passthrough = True
        sys.stdin = open(
            0)  # omg why is this not the first thing that pops up when searching for EOFError, i spent like 5h on this crap
        while True:
            if Windows.check_process("grw.exe"):
                if first_passthrough:
                    os.remove(Windows.expand_path("TEMP", "first_passthrough_flag.flag"))
                    first_passthrough = False
                time.sleep(5)
            elif os.path.isfile(
                    Windows.expand_path("TEMP", "first_passthrough_flag.flag")):  # find cleaner implementation
                logger.info("Initiating 3 minute grace period before game exit checks...")
                os.remove(Windows.expand_path("TEMP", "first_passthrough_flag.flag"))
                time.sleep(60 * 3)
            else:
                Script.suspend_process(pid_list)
                logger.warning("No running iteration of Ghost Recon: Wildlands detected. Initating backup options...")
                time.sleep(0.05)
                input_back_files = Script.input_log(
                    r"Do you want to keep the utility running and relaunch game? Enter r to restore but not relaunch, enter m for manual restore, w for manual restore without relaunch. (y/n/r/m/w)")
                while input_back_files.lower() not in "ynrmw":
                    logger.warning(
                        "Please enter a valid input: (y/n/r/m/w)")  # Maybe find less nonsensical names for the alternative options?
                    input_back_files = Script.input_log(
                        r"Do you want to keep the utility running and relaunch game? Enter r to restore but not relaunch, enter m for manual restore, w for manual restore without relaunch. (y/n/r/m/w)")
                if input_back_files.lower() == "y":
                    restore_savegames(options_index_to_restore, options_savegame_dir)
                    relaunch(gameinstallation_is_ubisoft, gameinstallation_is_steam, options_install_location)
                    Script.unsuspend_process(pid_list)
                elif input_back_files.lower() == "n":
                    exit_routine(pid_list)
                elif input_back_files.lower() == "r":
                    restore_savegames(options_index_to_restore, options_savegame_dir)
                    exit_routine(pid_list)
                elif input_back_files.lower() == "w":
                    manual_restore(options_index_to_restore, options_savegame_dir)
                    exit_routine(pid_list)
                elif input_back_files.lower() == "m":
                    manual_restore(options_index_to_restore, options_savegame_dir)
                    relaunch(gameinstallation_is_ubisoft, gameinstallation_is_steam, options_install_location)
                    Script.unsuspend_process(pid_list)

    @staticmethod
    def keyboard_listener(options_is_tab2m_remap_on):
        Script.logger_initialize(is_install=False)

        def on_press(key):
            key_str = str(key).replace("'", "")
            if key_str == "Key.tab" and options_is_tab2m_remap_on and Windows.getForegroundWindowTitle() == "Ghost Recon: Wildlands":  # TODO: Check if WinTitle of grw is in fact Ghost:Recon Wildlands
                keyboard.Controller().press('m')
                keyboard.Controller().release('m')
            if key_str == "\"" and Windows.getForegroundWindowTitle() == "Ghost Recon: Wildlands":
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
            if data.vkCode == 0x09 and options_is_tab2m_remap_on and Windows.getForegroundWindowTitle() == "Ghost Recon: Wildlands":  # tab key
                k_listener._suppress = True
            elif data.vkCode == 0xC0 and Windows.getForegroundWindowTitle() == "Ghost Recon: Wildlands":  # " key
                k_listener._suppress = True
            else:
                k_listener._suppress = False
            return True

        with keyboard.Listener(on_press=on_press, win32_event_filter=win32_event_filter, supress=False) as k_listener:
            k_listener.join()


class Options:  # for the ini
    install_location = None
    is_tab2m_remap_on = None
    index_to_restore = None
    backup_interval = None
    savegame_dir = None
    list_of_options = ["install_location", "is_tab2m_remap_on", "index_to_restore", "backup_interval", "savegame_dir"]

    @staticmethod
    def executable_check(folder):
        for file in os.listdir(folder.rstrip(r"\grw.exe")):
            if file == "grw.exe":
                return True
        return False

    @staticmethod
    def remap_question():
        tab_answer = Script.input_log("Do you want to remap M to Tab to change the map key in-game? (y/n)")
        while tab_answer.lower() != "y" and tab_answer.lower() != "n":
            logger.warning("Please enter a correct input: (y/n)")
            time.sleep(0.05)
            tab_answer = Script.input_log("Do you want to remap M to Tab to change the map key in-game? (y/n)")
        if tab_answer.lower() == "y":
            Options.is_tab2m_remap_on = True
            return
        else:
            Options.is_tab2m_remap_on = False
            return

    @staticmethod
    def index_question(called_recursively=False):
        if not called_recursively:
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
        ynwatcher = Script.input_log(
            f"""This equates to the script autorestoring a savegame from {minutes_conf_message} {"minutes" if minutes_conf_message != 1 else "minute"} ago, are you sure? (y/n)""") if int(
            index_answer * Options.backup_interval / 60) > 0 else Script.input_log(
            f"""This equates to the script autorestoring a savegame from {seconds_conf_message} {"seconds" if seconds_conf_message != 1 else "second"} ago, are you sure? (y/n)""")
        while ynwatcher.lower() != "y" and ynwatcher.lower() != "n":
            logger.warning("Please enter a correct input: (y/n)")
            time.sleep(0.05)
            Options.index_question(called_recursively=True)
            return
        if ynwatcher.lower() == "y":
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
    def initialize():
        config = configparser.ConfigParser()
        config.read(Windows.expand_backup_path("options.ini"))
        for e in Options.list_of_options:
            setattr(Options, e, config["Options"][e])

    @staticmethod
    def write_to_ini():
        config = configparser.ConfigParser()
        if os.path.isfile(Windows.expand_backup_path("options.ini")):
            config.read(Windows.expand_backup_path("options.ini"))
        else:
            open(Windows.expand_backup_path("options.ini"), 'a').close()  # create ini
            config.read(Windows.expand_backup_path("options.ini"))
            config["Options"] = {}
        for e in Options.list_of_options:
            config["Options"][e] = str(getattr(Options, e))
        with open(Windows.expand_backup_path("options.ini"), 'w') as configfile:  # save
            config.write(configfile)


if __name__ == "__main__":  # init

    if os.path.isdir(BACKUP_DIR):
        Script.logger_initialize(is_install=False)
        Script.updater()
        Options.initialize()
    else:
        Script.logger_initialize(is_install=True)
        logger.info("No prior installation of Wilthon detected. Initiating installation...")
        Script.install()

    processes = []
    num_processes = os.cpu_count()

    # create processes with setting first passthrough flag
    Routine.initialize()
    p1 = Process(target=Routine.back_savegames_up, args=(Options.savegame_dir, Options.backup_interval))
    p2 = Process(target=Routine.delete_unneccesary_backups)
    p3 = Process(target=Routine.handle_game_exits, args=(
        Script.pid_list, Options.index_to_restore, Options.savegame_dir, GameInstallation.is_steam,
        GameInstallation.is_ubisoft, Options.install_location))
    p4 = Process(target=Routine.keyboard_listener, args=(Options.is_tab2m_remap_on,))

    processes.append(p1)
    processes.append(p2)
    processes.append(p4)
    processes.append(p3)  # start handle game exits last so every pid gets passed in correctly

    for process in processes:  # start processes and get their pids
        process.start()
        Script.add_pid(process.pid)

    # block the main thread until these processes are finished
    for process in processes:
        process.join()

