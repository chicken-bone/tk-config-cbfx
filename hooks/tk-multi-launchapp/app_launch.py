"""
App Launch Hook

This hook is executed to launch the applications.
"""

import os
import sys
import sgtk


class AppLaunch(sgtk.Hook):
    """
    Hook to run an application.
    """

    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        """
        The execute function of the hook will be called to start the required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None
        :param engine_name: (str) The name of the engine associated with the
            software about to be launched.

        :returns: (dict) The two valid keys are 'command' (str) and 'return_code' (int).
        """
        

        # get the tank_name for the project
        ctx = self.sgtk.context_from_path(self.sgtk.project_path)
        project = self.sgtk.shotgun.find_one(
            "Project", [["id", "is", ctx.project["id"]]], ["tank_name"]
        )
        tank_name = project["tank_name"]
        prompt_flag = ""

        if sgtk.util.is_linux():
            # on Linux, we launch a gnome terminal in debug mode
            if kwargs.get('show_prompt') or os.getenv('TK_DEBUG'):
                cmd = f"""gnome-terminal -- bash -c "vfxjob-init {tank_name} -c "{app_path} {app_args}" ; exec bash" """
            else:
                cmd = f"""bash -c "vfxjob-init {tank_name} -c "{app_path} {app_args}"" &"""

        elif sgtk.util.is_windows():
            # on Windows, we run the start command.
            if not kwargs.get("show_prompt") and not os.getenv("TK_DEBUG"):
                # if we're NOT in debug mode we use the the /B flag which suppress
                # the cmd window
                prompt_flag = "/B "

            cmd = f"""start {prompt_flag}"App" "vfxjob-init {tank_name} -c "{app_path} {app_args}"" """

        else:
            # Handle unknown systems
            self.logger.warning(f"Unsupported operating system: {sys.platform}")
            return {"command": None, "return_code": 1}

        # run the command to launch the app
        exit_code = os.system(cmd)

        return {
            "command": cmd,
            "return_code": exit_code
        }