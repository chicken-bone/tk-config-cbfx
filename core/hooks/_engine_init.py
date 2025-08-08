# /shows/SAV/pipe/sgtk/config/core/hooks/engine_init.py

import sgtk
import os
try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    tk = None  # Fallback for environments without tkinter

class EngineInitHook(sgtk.Hook):
    """
    Hook executed when a Toolkit engine initializes.
    Checks critical ShotGrid project settings and shows a dialog if missing.
    """
    def execute(self, engine, prev_engine_name, **kwargs):
        """
        Executed by Toolkit during engine initialization.
        
        Args:
            engine: The current engine instance (e.g., tk-shotgun, tk-nuke).
            prev_engine_name: Name of the previous engine (if switching), or None.
            **kwargs: Additional arguments from the engine init process.
        """
        if not engine:
            # Log error if no engine is provided
            sgtk.LogManager().global_instance().error("No engine available during initialization.")
            return

        context = engine.context
        if not context or not context.project:
            engine.log_warning("No project context available during engine init.")
            return

        project_id = context.project["id"]
        sg = engine.shotgun
        if not sg:
            engine.log_error("No ShotGrid API instance available.")
            return

        # Fetch all project fields
        project_schema = sg.schema_field_read("Project")
        all_fields = list(project_schema.keys())
        project_data = sg.find_one("Project", [["id", "is", project_id]], all_fields)
        if not project_data:
            engine.log_error(f"No project data returned for ID: {project_id}")
            return

        # Filter out unwanted fields
        exclude_fields = {"landing_page_url", "image", "image_blur_hash"}
        project_data_filtered = {
            k: v for k, v in project_data.items()
            if k not in exclude_fields and not k.startswith("custom_non_project_entity")
        }

        # Check critical settings
        critical_fields = {
            "sg_fps": "Default FPS",
            "sg_type": "Type",
            "code": "Pipeline Code",
            "sg_default_format": "Default Format"
        }
        missing_settings = []
        for field_key, field_label in critical_fields.items():
            value = project_data_filtered.get(field_key)
            is_empty = value is None or (isinstance(value, (list, str, dict)) and not value)
            if is_empty:
                missing_settings.append(field_label)

        if missing_settings:
            warning_message = (
                'The following critical project settings are "Empty" or set to "None":\n\n- ' +
                "\n- ".join(missing_settings) +
                "\n\nThese must be set in Flow Production Tracking on the Project's Overview page, "
                "for other pipeline tools to work properly. Please contact your Producer to fix this issue."
            )

            # Try to show a dialog with tkinter
            if tk and "DISPLAY" in os.environ:
                try:
                    root = tk.Tk()
                    root.withdraw()  # Hide the root window
                    messagebox.showwarning("Critical Settings Missing", warning_message)
                    root.destroy()
                except Exception as e:
                    engine.log_warning(f"Failed to show tkinter dialog: {str(e)}. Falling back to log.")
                    engine.log_warning(warning_message)
            else:
                # Fallback to logging if no GUI or tkinter unavailable
                engine.log_warning("No GUI environment detected or tkinter unavailable.")
                engine.log_warning(warning_message)
