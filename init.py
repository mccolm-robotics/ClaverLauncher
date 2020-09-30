import importlib
import json
import logging
import os
import subprocess
import sys
import time

"""
NOTE:
Target system must have python > 3.6 installed
Target system must have pip3 installed and a symlink pointing to pip
Target system must have virtualenv installed
Target system must have curl installed
"""

class Init:
    def __init__(self):
        self.config = None      # A dictionary representation of JSON data describing the app
        self.application = None     # Holds an instance of the entry_point class for the application loaded from the github repository linked below
        self.clock = int(time.time())   # Unix timestamp used as a name for the cloned git repository
        self.venv_interpreter = os.getcwd() + "/venv/bin/python"    # Path to the virtual environment Python interpreter
        self.required_modules = ["requests"]  # List of 3rd party modules required by the Claver launcher
        self.repository_host_url = "https://github.com/mccolm-robotics/"
        self.repository_raw_host_url = "https://raw.githubusercontent.com/mccolm-robotics/"
        self.client_app_repo_branch = "stable"   # Default branch of the git repository to load
        self.client_app_repo_name = "ClaverNode" # Name of the git repository to load
        self.client_app_repo_class_name = self.client_app_repo_name   # Name of the entry_point class for the application
        self.client_app_repo_url = self.repository_host_url + self.client_app_repo_name + ".git"     # Repository URL
        self.launcher_repo_branch = "stable"
        self.launcher_repo_name = "ClaverLauncher"
        self.launcher_repo_url = self.repository_host_url + self.launcher_repo_name + ".git"
        self.action_request = None    # Exit status for the client app run by the launcher
        if os.path.isfile("config.txt"):    # Check to see if config file already exists
            self.load_config_file("config.txt")     # Read in file (JSON)
            self.client_app_repo_name = self.config["app_dir"]   # Set the repository name to value stored in config file
        self.setup_logging(console=logging.INFO)    # Set the logging level for launcher. DEBUG == verbose
        self.install_launcher_dependencies(["psutil"])  # Make sure module 'psutil' is installed
        self.run_launcher()

    def install_launcher_dependencies(self, dependency_list:list):
        """ Install launcher dependencies """
        for dep in dependency_list:
            module_check = subprocess.run(["pip", "show", dep], capture_output=True, encoding="utf-8")
            if not module_check.stdout:
                self.logger.info(f"Installing {dep}")
                module_install = subprocess.run(["pip", "install", "--user", dep], stdout=subprocess.PIPE, text=True, check=True)
                if module_install.returncode:
                    self.logger.error(f"Error: Unable to install {dep} module")

    def run_launcher(self):
        ''' Main entry-point for launcher execution '''
        self.check_for_launcher_update()
        self.activate_venv()    # Ensures virtual environment is installed and switches over to it.
        if self.download_client_app():  # Ensures a version of the app has been downloaded and configured to run
            self.launch_client_app()   # Instantiantes and loads app (based on repo name) and deletes previously installed versions
        self.evaluate_client_app_action_request()  # Checks for messages sent back from the app
        self.save_config_file()    # Saves app config-state to config.txt

    def check_for_launcher_update(self):
        local_version, remote_version = self.get_launcher_version_numbers()
        print(f"local: {local_version}; remote: {remote_version}")

    def activate_venv(self):
        """ Activates the virtual environment. This function restarts the app and switches over to using the venv interpreter. """
        # Check to see if the launcher is running with the default Python interpreter or the virtual environment interpreter
        if sys.executable != self.venv_interpreter: # Check to see of the app is using the system interpreter.
            import psutil   # Make module available in this function
            if not os.path.isdir("venv"):   # Does the virtual environment folder exist?
                if os.path.isdir(self.client_app_repo_name):     # Check to see the repository folder exists. If so, venv has been deleted. Reload repository from stable branch.
                    subprocess.run(["rm", "-r", self.client_app_repo_name], stdout=subprocess.PIPE, text=True, check=True)   # Remove previous repository directory
                    if os.path.isfile("config.txt"):    # Remove old config.txt as it is now outdated
                        subprocess.run(["rm", "config.txt"], stdout=subprocess.PIPE, text=True, check=True)     # Remove previous config file
                create_venv = subprocess.run(["virtualenv", "venv"], stdout=subprocess.PIPE, text=True, check=True) # Create a new virtual environment
                if create_venv.returncode:
                    self.logger.error("Error: Failed to create VirtualEnv")
            try:
                p = psutil.Process(os.getpid())     # Get the current process id of this launcher
                for handler in p.open_files() + p.connections():    # Close any open files and connections held by this process
                    os.close(handler.fd)
            except Exception as e:
                self.logger.error("Error: Unable to close files and connections held by process", exc_info=True)
            # Relaunch application using virtual environment interpreter
            os.execl(self.venv_interpreter, self.venv_interpreter, *sys.argv)
        else:
            # Executes after application has restarted. Changes path variables to point to venv interpreter.
            exec(open("venv/bin/activate_this.py").read(), {'__file__': "venv/bin/activate_this.py"})
            if self.required_modules:   # List of modules required by this launcher
                self.logger.debug("Updating modules required by launcher")
                for module in self.required_modules:    # Install required modules using pip
                    proc = subprocess.run(["pip", "install", module], capture_output=True, encoding="utf-8")
                    self.logger.debug(proc.stdout)
            installed_modules = subprocess.run(["pip", "list"], capture_output=True, encoding="utf-8")  # Get a list of installed modules registered by pip
            result = installed_modules.stdout
            # result = ' '.join(result.split())
            # result = result[35:]
            # i = iter(result.split(' '))
            # ClaverNode = list(map(" ".join, zip(i, i)))
            self.logger.debug(result)

    def setup_logging(self, console=logging.INFO, file=logging.WARNING):
        """ Set logger to capture different levels of information. Data logged to file differs (depending on settings) from data displayed to the console (stdout). """
        if not os.path.isdir("logs"):   # Check to see if the logs directory exists
            os.mkdir("logs")    # Create the directory
        if os.path.isfile('logs/' + self.client_app_repo_name + '.log'):  # Logs will be retained on a per-run basis. Delete log from previous run.
            os.remove('logs/' + self.client_app_repo_name + '.log')
        # The first run of this program will create a log with the name of the repository.
        if os.path.isfile('logs/' + self.client_app_repo_class_name + '.log'):  # Logs will be retained on a per-run basis. Delete log from previous run.
            os.remove('logs/' + self.client_app_repo_class_name + '.log')
        # Reset any previous locks on the logger
        logging.getLogger().setLevel(logging.DEBUG)
        logger = logging.getLogger('')
        logger.handlers = []

        self.logger = logging.getLogger(__name__)   # Set logger to name of module
        # Create handlers
        c_handler = logging.StreamHandler(stream=sys.stdout)    # Create console logger
        f_handler = logging.FileHandler('logs/' + self.client_app_repo_name + '.log')    # Create file logger
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

        self.logger.warning(f'Log initialized for {self.client_app_repo_name}') # The minimum logging level for the file logger is set to WARNING

    def restart_launcher(self):
        """ Restarts the current program """
        import psutil
        try:
            p = psutil.Process(os.getpid())
            for handler in p.open_files() + p.connections():
                os.close(handler.fd)
        except Exception as e:
            self.logger.error("Error: Unable to close files and connections held by process", exc_info=True)
        # Relaunch application using virtual environment interpreter
        os.execl(self.venv_interpreter, self.venv_interpreter, *sys.argv)

    def load_config_file(self, config):
        """ Read in the contents of JSON file (config.txt) """
        with open(config) as file:
            self.config = json.load(file)

    def save_config_file(self):
        """ Save config information in JSON format to config.txt """
        with open('config.txt', 'w') as outfile:
            json.dump(self.config, outfile, indent=2, sort_keys=True)

    def load_local_version_number(self, path):
        """ Loads the version file from the local copy of the module and returns its values as a dictionary """
        with open(path) as file:
            return json.load(file)

    def load_repository_version_number(self, path):
        """ Downloads the version file from the remote copy of the module and returns its values as a dictionary """
        import requests     # Make module available for this function
        response = requests.get(path)
        if response.status_code < 400:  # Make sure that the file was accessible
            return response.json()
        else:
            return False

    def check_for_module_update(self, remote_version, local_version) -> bool:
        """ Compares version values between local and remote copies of client module """
        # Compare version numbers
        if int(remote_version["MAJOR"]) > int(local_version["MAJOR"]) \
                or int(remote_version["MINOR"]) > int(local_version["MINOR"]) \
                or int(remote_version["PATCH"]) > int(local_version["PATCH"]):
            return True     # Initiate upgrade
        else:
            return False

    def download_client_app(self):
        """ Ensures that a running copy of the app has been downloaded. ToDo: Roll back any failed version. """
        if self.config is None:
            config = self.client_app_repo_name + "/src/config.txt"
            if not os.path.isfile(config):
                clone_git = subprocess.run(["git", "clone", "--single-branch", "--branch", self.client_app_repo_branch, self.client_app_repo_url, "t" + str(self.clock)], stdout=subprocess.PIPE, text=True, check=True)
                if clone_git.returncode:
                    self.logger.error(f"Error: Failed to clone app from {self.client_app_repo_url}: branch={self.client_app_repo_branch}")
                    return False
                self.client_app_repo_name = "t" + str(self.clock)   # Modules must not start with a number
                # Install modules listed in requirements.txt
                requirements_path = self.client_app_repo_name + "/requirements/requirements.txt"
                install_requirements = subprocess.run(["pip", "install", "-r", requirements_path], stdout=subprocess.PIPE, text=True, check=True)
                if install_requirements.returncode:
                    self.logger.error("Error: Failed to load requirements.txt")
                    return False
                # Update path of config.txt
                config = self.client_app_repo_name + "/src/config.txt"
                if not os.path.isfile(config):
                    self.logger.error("Failed to locate config file")
                    return False
                self.load_config_file(config)
                self.config["app_dir"] = self.client_app_repo_name   # Save the name of repository to config.txt
                self.config["version"] = self.load_local_version_number(self.client_app_repo_name + "/VERSION.txt")
        else:
            local_version, remote_version = self.get_client_app_version_numbers()
            if remote_version:  # Make sure the remote version file returned a value
                if self.check_for_module_update(remote_version, local_version):
                    self.logger.info("Downloading update")
                    self.upgrade_client_app()
        return True

    def get_client_app_version_numbers(self):
        # This value is only relevant when the client app module is loaded using a production build
        cmd = "curl -s https://api.github.com/repos/mccolm-robotics/" + self.client_app_repo_class_name + "/releases/latest | grep -oP '\"tag_name\": \"\K(.*)(?=\")'"
        ps = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        release_ver = ps.communicate()[0]
        print(release_ver.decode())

        local_version = self.load_local_version_number(self.client_app_repo_name + "/VERSION.txt")
        # URL of version text file in remote repository
        repository_path = self.repository_raw_host_url + self.client_app_repo_class_name + "/" + self.client_app_repo_branch + "/" + "VERSION.txt"
        remote_version = self.load_repository_version_number(repository_path)
        return local_version, remote_version

    def get_launcher_version_numbers(self):
        local_version = self.load_local_version_number("VERSION.txt")
        # URL of version text file in remote repository
        repository_path = self.repository_raw_host_url + self.launcher_repo_name + "/" + self.launcher_repo_branch + "/" + "VERSION.txt"
        print(repository_path)
        remote_version = self.load_repository_version_number(repository_path)
        return local_version, remote_version

    def upgrade_client_app(self):
        """ Download the newest version of the client app and restart app. """
        clone_git = subprocess.run(["git", "clone", "--single-branch", "--branch", self.client_app_repo_branch, self.client_app_repo_url, "t" + str(self.clock)], stdout=subprocess.PIPE, text=True, check=True)
        if clone_git.returncode:
            self.logger.error(f"Error: Failed to clone app from {self.client_app_repo_url}: branch={self.client_app_repo_branch}")
            return False
        # Modules must not start with a number
        self.client_app_repo_name = "t" + str(self.clock)
        # Install modules listed in requirements.txt
        requirements_path = self.client_app_repo_name + "/requirements/requirements.txt"
        install_requirements = subprocess.run(["pip", "install", "-r", requirements_path], stdout=subprocess.PIPE, text=True, check=True)
        if install_requirements.returncode:
            self.logger.error("Error: Failed to load requirements.txt")
            return False
        self.config["previous_app_dir"] = self.config["app_dir"]
        self.config["app_dir"] = self.client_app_repo_name
        self.save_config_file()
        self.restart_launcher()

    def client_app_exit_status(self, val, **kwargs):
        """ Callback function passed to application module. GTK does not allow setting the exit status directly. """
        self.action_request = val

    def launch_client_app(self):
        """ Dynamically loads app based on repository name. Assumes main class matches repository name. Deletes previously installed version of the app. """
        # Import the module
        mod = importlib.import_module(f'{self.client_app_repo_name}.src.{self.client_app_repo_class_name}')
        # Determine a list of names to copy to the current name space
        names = getattr(mod, '__all__', [n for n in dir(mod) if not n.startswith('_')])
        # Copy the name of the entry-point class into the current name space
        g = globals()
        for name in names:
            # Look for the class that matches the repository name
            if name == self.client_app_repo_class_name:
                entry_point = getattr(mod, name)
                g[name] = entry_point
        self.application = entry_point(self.client_app_exit_status)    # Instantiate app class
        self.config["app_exit_status"] = self.application.run()     # Entry-point for GTK applications is run()
        if "previous_app_dir" in self.config \
                and not self.config["app_exit_status"] \
                and os.path.isdir(self.config["previous_app_dir"]): # If app ran without error (exit-status == 0), check for previous version of app and delete directory
            self.logger.info("Removing previous version directory")
            subprocess.run(["rm", "-r", self.config["previous_app_dir"]], stdout=subprocess.PIPE, text=True, check=True)
            if os.path.isfile('logs/' + self.config["previous_app_dir"] + '.log'):  # Logs will be retained on a per-run basis. Delete log from previous run.
                os.remove('logs/' + self.config["previous_app_dir"] + '.log')
            if not os.path.isdir(self.config["previous_app_dir"]):  # Make sure the directory was deleted
                del self.config["previous_app_dir"]     # Remove key from the config dictionary

    def evaluate_client_app_action_request(self):
        """ Action any requests sent by the app """
        self.config["action_request"] = self.action_request
        self.logger.info(f"Exit Status: {self.action_request}")
        if self.action_request is None:
            self.logger.error("App failed to start")
            # ToDo: Implement roll-back if FAIL follows update to new version
            # ToDo: Save log file and upload to server / email to maintainer
        elif self.action_request == 0:
            print("No actionable requests sent")
        elif self.action_request == 1:
            print("Request to upgrade app")
            self.upgrade_client_app()


if __name__ == "__main__":
    Init()


"""
Resources: Using Shell Commands
https://stackabuse.com/executing-shell-commands-with-python/
https://queirozf.com/entries/python-3-subprocess-examples
https://stackoverflow.com/questions/2502833/store-output-of-subprocess-popen-call-in-a-string

Resources: Reading/Writing JSON Files
https://stackabuse.com/reading-and-writing-json-to-a-file-in-python/

Resources: Git
https://devconnected.com/how-to-clone-a-git-repository/
https://gist.github.com/rponte/fdc0724dd984088606b0
https://stackoverflow.com/questions/4630704/receiving-fatal-not-a-git-repository-when-attempting-to-remote-add-a-git-repo
https://stackoverflow.com/questions/15472107/when-listing-git-ls-remote-why-theres-after-the-tag-name/15472310
https://medium.com/@ginnyfahs/github-error-authentication-failed-from-command-line-3a545bfd0ca8  <- Using personal access tokens on cli
https://stackoverflow.com/questions/4565700/how-to-specify-the-private-ssh-key-to-use-when-executing-shell-command-on-git
https://gist.github.com/jexchan/2351996 <- Configure multiple SSH Keys for GitHub accounts
https://kamarada.github.io/en/2019/07/14/using-git-with-ssh-keys/ <- Creating SSH Keys
https://stackoverflow.com/questions/46226174/getting-git-init-to-automatically-use-ssh <- Using SSH instead of https authentication for git processes
https://gist.github.com/steinwaywhw/a4cd19cda655b8249d908261a62687f8 <- Getting the latest release version number
https://devconnected.com/how-to-delete-local-and-remote-tags-on-git/
https://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package/2073599#2073599
https://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package
https://stackoverflow.com/questions/17583443/what-is-the-correct-way-to-share-package-version-with-setup-py-and-the-package
https://packaging.python.org/guides/single-sourcing-package-version/
https://www.digitalocean.com/community/tutorials/how-to-package-and-distribute-python-applications
https://medium.com/@amimahloof/how-to-package-a-python-project-with-all-of-its-dependencies-for-offline-install-7eb240b27418
https://www.jetbrains.com/help/pycharm/creating-and-running-setup-py.html

Resources: Python Packaging
https://python-packaging-tutorial.readthedocs.io/en/latest/setup_py.html
https://github.com/ceddlyburge/python_world/blob/master/setup.py

Resources: Pip
https://stackoverflow.com/questions/11248073/what-is-the-easiest-way-to-remove-all-packages-installed-by-pip
https://medium.com/@arocketman/creating-a-pip-package-on-a-private-repository-using-setuptools-fff608471e39
https://dev.to/rf_schubert/how-to-create-a-pip-package-and-host-on-private-github-repo-58pa
https://www.freecodecamp.org/news/how-to-use-github-as-a-pypi-server-1c3b0d07db2/
https://hackthology.com/how-to-write-self-updating-python-programs-using-pip-and-git.html

Resources: Import module dynamically
https://stackoverflow.com/questions/31306469/import-from-module-by-importing-via-string/31306598#31306598
https://stackoverflow.com/questions/301134/how-to-import-a-module-given-its-name-as-string

Resources: URL Requests
https://stackoverflow.com/questions/16778435/python-check-if-website-exists
"""