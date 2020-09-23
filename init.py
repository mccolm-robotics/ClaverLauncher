import importlib
import json
import os
import subprocess
import sys
import time


class Init:
    def __init__(self):
        self.config = None      # A dictionary representation of JSON data describing the app
        self.application = None     # Holds an instance of the entry_point class for the application loaded from the github repository linked below
        self.clock = int(time.time())   # Unix timestamp used as a name for the cloned git repository
        self.venv_interpreter = os.getcwd() + "/venv/bin/python"    # Path to the virtual environment copy of the Python intrepreter
        self.required_modules = []  # List of 3rd party modules required by the Claver launcher
        self.repository_branch = "stable"   # Default branch of the git repository to load
        self.repository_name = "ClaverNode" # Name of the git repository to load
        self.repository_class_name = self.repository_name   # Name of the entry_point class for the application
        self.repository_url = "https://github.com/mccolm-robotics/" + self.repository_name + ".git"     # Repository URL
        self.exit_status = 0    # Default exit status for the application

        if os.path.isfile("config.txt"):
            self.load_config_file("config.txt")
            self.repository_name = self.config["dir"]
        self.run()      # Run the launcher

    def run(self):
        ''' Main execution area of launcher '''
        self.activate_venv()    #
        if self.load_client_app():
            self.launch_app()
        self.evaluate_exit_status()
        # Update config with successful run status

    def activate_venv(self):
        ''' Activates the virtual environment. This function restarts the app and switches over to using the venv interpreter. '''

        # Check to see if the launcher is running with the default Python interpreter or the virtual environment interpreter
        if sys.executable != self.venv_interpreter:
            # Make sure psutil is installed
            psutil_check = subprocess.run(["pip", "show", "psutil"], capture_output=True, encoding="utf-8")
            if not psutil_check.stdout:
                print("Installing psutil")
                psutil_install = subprocess.run(["pip", "install", "--user", "psutil"], stdout=subprocess.PIPE, text=True, check=True)
                if psutil_install.returncode:
                    print("Error: Unable to install psutil module")

            import psutil

            if not os.path.isdir("venv"):
                if os.path.isdir(self.repository_name):
                    subprocess.run(["rm", "-r", self.repository_name], stdout=subprocess.PIPE, text=True, check=True)
                    if os.path.isfile("config.txt"):
                        subprocess.run(["rm", "config.txt"], stdout=subprocess.PIPE, text=True, check=True)

                create_venv = subprocess.run(["virtualenv", "venv"], stdout=subprocess.PIPE, text=True, check=True)
                if create_venv.returncode:
                    print("Error: Failed to create VirtualEnv")

            try:
                p = psutil.Process(os.getpid())
                for handler in p.open_files() + p.connections():
                    os.close(handler.fd)
            except Exception as e:
                # logging.error(e)
                pass

            # Relaunch application using virtual environment interpreter
            os.execl(self.venv_interpreter, self.venv_interpreter, *sys.argv)
        else:
            # Executes after application has restarted
            exec(open("venv/bin/activate_this.py").read(), {'__file__': "venv/bin/activate_this.py"})

            if self.required_modules:
                print("Updating modules required by launcher")
                for module in self.required_modules:
                    proc = subprocess.run(["pip", "install", module], capture_output=True, encoding="utf-8")
                    print(proc.stdout)

            print("Modules currently installed:")
            installed_modules = subprocess.run(["pip", "list"], capture_output=True, encoding="utf-8")
            result = installed_modules.stdout
            # result = ' '.join(result.split())
            # result = result[35:]
            # i = iter(result.split(' '))
            # ClaverNode = list(map(" ".join, zip(i, i)))
            print(result)


    def restart_program(self):
        """ Restarts the current program """
        import psutil

        try:
            p = psutil.Process(os.getpid())
            for handler in p.open_files() + p.connections():
                os.close(handler.fd)
        except Exception as e:
            # logging.error(e)
            pass

        python = sys.executable
        os.execl(python, python, *sys.argv)

    def load_config_file(self, config):
        with open(config) as file:
            self.config = json.load(file)

    def save_config_file(self):
        with open('config.txt', 'w') as outfile:
            json.dump(self.config, outfile)

    def load_client_app(self):
        ''' Ensures that a running copy of the app has been downloaded. Rolls back any failed version. '''
        # if not os.path.isfile("config.txt"):    # Checks to see if any version has run previously.
        if self.config is None:
            config = self.repository_name + "/src/config.txt"
            if not os.path.isfile(config):
                clone_git = subprocess.run(["git", "clone", "--single-branch", "--branch", self.repository_branch, self.repository_url, "t" + str(self.clock)], stdout=subprocess.PIPE, text=True, check=True)
                if clone_git.returncode:
                    print(f"Error: Failed to clone app from {self.repository_url}: branch={self.repository_branch}")
                    return False

                # Modules must not start with a number
                self.repository_name = "t" + str(self.clock)

                # Install modules listed in requirements.txt
                requirements_path = self.repository_name + "/requirements/requirements.txt"
                install_requirements = subprocess.run(["pip", "install", "-r", requirements_path], stdout=subprocess.PIPE, text=True, check=True)
                if install_requirements.returncode:
                    print("Error: Failed to load requirements.txt")
                    return False

                # Set location of config.txt
                config = self.repository_name + "/src/config.txt"
                if not os.path.isfile(config):
                    print("Failed to locate config file")
                    return False

                self.load_config_file(config)
                self.config["dir"] = self.repository_name   # Save the name of repository to config.txt
                self.save_config_file()

        # else:
            # self.load_config_file("config.txt")
            # self.repository_name = self.config["dir"]
            # ToDo: Check to see if the last run attempt was successful

        return True

    def set_exit_status(self, val):
        ''' Callback function passed to application module. GTK does not allow setting the exit status directly. '''
        self.exit_status = val

    def launch_app(self):
        # Import the module
        mod = importlib.import_module(f'{self.repository_name}.src.launcher')

        # Determine a list of names to copy to the current name space
        names = getattr(mod, '__all__', [n for n in dir(mod) if not n.startswith('_')])

        # Add the name of the entry-point class into the current name space
        g = globals()
        for name in names:
            # Look for the class that matches the repository name
            if name == self.repository_class_name:
                entry_point = getattr(mod, name)
                g[name] = entry_point

        self.application = entry_point(self.set_exit_status)
        self.application.run()

    def evaluate_exit_status(self):
        print(f"Exit Status: {self.exit_status}")
        if self.exit_status == 1:
            print("Taking action for status # 1")

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

Resources: Python Packaging
https://python-packaging-tutorial.readthedocs.io/en/latest/setup_py.html
https://github.com/ceddlyburge/python_world/blob/master/setup.py

Resources: Pip
https://stackoverflow.com/questions/11248073/what-is-the-easiest-way-to-remove-all-packages-installed-by-pip
https://medium.com/@arocketman/creating-a-pip-package-on-a-private-repository-using-setuptools-fff608471e39
https://dev.to/rf_schubert/how-to-create-a-pip-package-and-host-on-private-github-repo-58pa
https://www.freecodecamp.org/news/how-to-use-github-as-a-pypi-server-1c3b0d07db2/
https://hackthology.com/how-to-write-self-updating-python-programs-using-pip-and-git.html

"""