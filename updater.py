import json
import logging
import os
import sys
import requests


class Updater:
    def __init__(self):
        self.config = None  # A dictionary representation of JSON data describing the app
        self.repository_raw_host_url = "https://raw.githubusercontent.com/mccolm-robotics/"
        self.launcher_repo_branch = "stable"
        self.launcher_repo_name = "ClaverLauncher"
        self.updater_log = "updater"
        self.setup_logging()
        if os.path.isfile("config.txt"):    # Check to see if config file already exists
            self.load_config_file("config.txt")     # Read in file (JSON)
        self.config["launcher_updated"] = self.launcher_repo_branch
        self.run_updater()

    def run_updater(self):
        """ Main entry-point of class """
        repository_url = self.repository_raw_host_url + self.launcher_repo_name + "/" + self.launcher_repo_branch

        self.rename_file(current_name="init.py", new_name="old_init.py")
        self.config["previous_launcher"] = "old_init.py"
        self.config["previous_launcher_version"] = self.load_version_file("VERSION.txt")
        self.rename_file(current_name="VERSION.txt", new_name="OLD_VERSION.txt")
        self.save_remote_file(repository_url + "/init.py", "init.py")
        self.save_remote_file(repository_url + "/VERSION.txt", "VERSION.txt")

        # Restart launcher
        self.save_config_file()
        module_path = os.getcwd() + "/init.py"
        self.start_launcher(module_path)

    def save_remote_file(self, url, file_name):
        remote_file = requests.get(url)
        if remote_file.status_code < 400:
            with open(file_name, 'wb') as file:
                file.write(remote_file.content)

    def rename_file(self, current_name, new_name):
        os.rename(current_name, new_name)  # Rename current init file
        self.logger.info(f"{current_name} renamed to {new_name}")

    def load_config_file(self, config):
        """ Read in the contents of JSON file (config.txt) """
        with open(config) as file:
            self.config = json.load(file)

    def load_version_file(self, version):
        """ Loads the version file from the local copy of the module and returns its values as a dictionary """
        with open(version) as file:
            return json.load(file)

    def save_config_file(self):
        """ Save config information in JSON format to config.txt """
        with open('config.txt', 'w') as outfile:
            json.dump(self.config, outfile, indent=2, sort_keys=True)

    def setup_logging(self, console=logging.INFO, file=logging.WARNING):
        """ Set logger to capture different levels of information. Data logged to file differs (depending on settings) from data displayed to the console (stdout). """
        if not os.path.isdir("logs"):   # Check to see if the logs directory exists
            os.mkdir("logs")    # Create the directory
        if os.path.isfile('logs/' + self.updater_log + '.log'):  # Logs will be retained on a per-run basis. Delete log from previous run.
            os.remove('logs/' + self.updater_log + '.log')

        # Reset any previous locks on the logger
        logging.getLogger().setLevel(logging.DEBUG)
        logger = logging.getLogger('')
        logger.handlers = []

        self.logger = logging.getLogger(__name__)   # Set logger to name of module
        # Create handlers
        c_handler = logging.StreamHandler(stream=sys.stdout)    # Create console logger
        f_handler = logging.FileHandler('logs/' + self.updater_log + '.log')    # Create file logger
        c_handler.setLevel(console)     # Set logging level for console logger
        f_handler.setLevel(file)        # Set logging level for file logger

        # Create formatters and add them to handlers
        c_format = logging.Formatter('%(message)s')
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the logger
        self.logger.addHandler(c_handler)
        self.logger.addHandler(f_handler)

        self.logger.warning(f'Log initialized for {self.updater_log}') # The minimum logging level for the file logger is set to WARNING

    def start_launcher(self, path):
        """ Restarts the current program """
        import psutil
        try:
            p = psutil.Process(os.getpid())
            for handler in p.open_files() + p.connections():
                os.close(handler.fd)
        except Exception as e:
            self.logger.error("Error: Unable to close files and connections held by process", exc_info=True)

        python = sys.executable
        os.execl(python, python, path)  # Relaunch application

if __name__ == "__main__":
    Updater()