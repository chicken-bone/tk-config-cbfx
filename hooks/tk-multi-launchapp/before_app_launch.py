# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Before App Launch Hook

This hook is executed prior to application launch and is useful if you need
to set environment variables or run scripts as part of the app initialization.
"""

import sgtk
import sys
import re
import os
from collections import defaultdict


class BeforeAppLaunch(sgtk.Hook):
    """
    Hook to set up the system prior to app launch.
    """
    __env_vars_entity = "CustomNonProjectEntity05"
    __version_regex = re.compile(r"(\d+)\.?(?:\d+)?(?:\.|v)?(\d+)?")

    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        """
        The execute function of the hook will be called prior to starting the required application.

        :param app_path: str, The path of the application executable.
        :param app_args: str, Any arguments the application may require.
        :param version: str, Version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None.
        :param engine_name: str, The name of the engine associated with the
            software about to be launched.
        """
        current_context = self.parent.context
        self._log_debug("engine_name", engine_name)
        self._log_debug("current_context", current_context)
        self._log_debug("user", current_context.user)
        self._log_debug("app_path", app_path)
        self._log_debug("app_args", app_args)
        self._log_debug("version", version)

        nx_fw = self.load_framework("tk-framework-nx_v0.x.x")
        nx_utils = nx_fw.import_module("utils")

        self._set_env_vars_from_templates(nx_utils, current_context)
        env_dicts = self.__get_env_vars(current_context, engine_name, version)

        self._apply_env_vars(env_dicts)
        self._update_task_status()

    def _log_debug(self, key, value):
        """Log debug information with a key-value format."""
        self.logger.debug(f"{key}: {value}")

    def _set_env_vars_from_templates(self, nx_utils, context):
        """Set environment variables from template configurations."""
        for key, template in {k: v for k, v in self.sgtk.templates.items() if k.startswith("pipe_")}.items():
            value = nx_utils.resolve_template(template, context)
            value = os.path.expandvars(value)
            os.environ[key.upper()] = value
            self._log_debug(f"Setting EnvVars from templates.yml", f"{key.upper()} = {value}")

    def _apply_env_vars(self, env_dicts):
        """Apply environment variables according to their method."""
        methods = ["replace", "prepend", "append"]
        env_keys = list(set(list(env_dicts['replace'].keys()) + 
                            list(env_dicts['prepend'].keys()) + 
                            list(env_dicts['append'].keys())))

        for key in env_keys:
            self.logger.debug(f"Appending to SGTK_ENV_VARS: {key}")
            sgtk.util.append_path_to_env_var("SGTK_ENV_VARS", os.path.expandvars(key))
        if os.getenv("TK_DEBUG"):
            sgtk.util.append_path_to_env_var("SGTK_ENV_VARS", "TK_DEBUG")
        self.logger.debug(f"SGTK_ENV_VARS after setting: {os.getenv('SGTK_ENV_VARS')}")

        for method in methods:
            for env_key, value_list in env_dicts[method].items():
                for env_value in value_list:
                    try:
                        env_value = os.path.expandvars(env_value)
                        self.logger.debug(f"Processing {method} for {env_key} with value: {env_value}")
                        if method == "replace":
                            os.environ[env_key] = env_value
                            self.logger.debug(f"Environment variable {env_key} set to: {env_value}")
                        elif method == "prepend":
                            sgtk.util.prepend_path_to_env_var(env_key, env_value)
                            self.logger.debug(f"Prepending {env_value} to {env_key}")
                        elif method == "append":
                            sgtk.util.append_path_to_env_var(env_key, env_value)
                            self.logger.debug(f"Appending {env_value} to {env_key}")
                    except Exception as e:
                        self.logger.error(f"Error setting {env_key} with {env_value} using method {method}: {e}")

        # Log all applied environment variables
        for method, env_dict in env_dicts.items():
            for env_key in env_dict.keys():
                self.logger.debug(f"Final value for {env_key}: {os.getenv(env_key)}")

    def _update_task_status(self):
        """Update the current task status to 'in progress' if it's ready."""
        if self.parent.context.task:
            task_id = self.parent.context.task['id']
            task = self.parent.sgtk.shotgun.find_one(
                "Task", 
                filters=[["id", "is", task_id]], 
                fields=["sg_status_list"]
            )
            self._log_debug(f"task {task_id} status", task['sg_status_list'])
            if task['sg_status_list'] == 'rdy':
                data = {'sg_status_list': 'ip'}
                self.parent.shotgun.update("Task", task_id, data)
                self._log_debug("Task status changed to", "'ip'")

    def __get_env_vars(self, context, engine_name, app_version):
        """Retrieve environment variables from Shotgun."""
        filters = self._build_filters(context, engine_name)
        os_envs = {'win32': 'sg_env_win', 'linux2': 'sg_env_linux', 'linux': 'sg_env_linux', 'darwin': 'sg_env_mac'}
        fields = ['code', 'sg_version', 'sg_host_min_version', 'sg_host_max_version', 'sg_default_method', os_envs[sys.platform]]

        results = self.parent.shotgun.find(self.__env_vars_entity, filters, fields)
        env_lists = {"append": [], "prepend": [], "replace": []}

        for result in results:
            platform_field = os_envs[sys.platform]
            if not result.get(platform_field):
                continue
            if self.__version_check(app_version, result.get('sg_host_min_version'), result.get('sg_host_max_version')):
                self._log_debug("Valid plugin found", result.get('code'))
                try:
                    env_vars = result.get(platform_field, "")
                    for env_var in env_vars.split('\n'):
                        if env_var.strip():
                            key, value = env_var.split('=', 1)
                            if value is None:
                                self.logger.warning(f"Environment variable {key} has None as value")
                            else:
                                env_lists[result.get('sg_default_method')].append(env_var)
                except AttributeError as e:
                    self.logger.error(f'AttributeError on plugin "{result.get("code")}": {e}')

        env_dicts = {"append": {}, "prepend": {}, "replace": {}}
        for method, env_list in env_lists.items():
            for env_var in env_list:
                try:
                    key, value = env_var.split('=', 1)
                    env_dicts[method].setdefault(key, []).append(value)
                except IndexError as e:
                    self.logger.error(f'IndexError on plugin "{result.get("code")}": {e}')

        self.__resolve_nested_vars(env_dicts)
        return env_dicts

    def __resolve_nested_vars(self, envs):
        """Resolve nested variables in environment settings."""
        ctx = self.parent.context
        entity = ctx.entity
        proj = entity.get('code') if entity and entity["type"] == "Project" else ''
        seq = entity.get('code') if entity and entity["type"] == "Sequence" else ''
        shot = entity.get('code') if entity and entity["type"] == "Shot" else ''
        asset = entity.get('code') if entity and entity["type"] == "Asset" else ''

        if not entity:
            proj_entity = self.parent.sgtk.shotgun.find_one(
                'Project', 
                filters=[['id', 'is', self.parent.context.project['id']]],
                fields=['code']
            )
            proj = proj_entity.get('code', '')

        for method in envs:
            for key, values in envs[method].items():
                new_values = []
                for v in values:
                    try:
                        resolved_v = v.replace('$SEQ', seq).replace('$SHOT', shot).replace('$SHOW', proj) \
                                      .replace('$PROJ', proj).replace('$ASSET', asset)
                        new_values.append(resolved_v)
                        self.logger.debug(f"Resolved {v} to {resolved_v}")
                    except Exception as e:
                        self.logger.error(f"Failed to resolve variable in {v}: {e}")
                envs[method][key] = new_values

    def __version_check(self, curr_version, min_version, max_version):
        """Check if current version is within the allowed range."""
        if min_version is None and max_version is None:
            return True
        
        def parse_version(version_str):
            match = self.__version_regex.match(version_str or '')
            return tuple(int(x or 0) for x in match.groups() if x is not None)

        curr = parse_version(curr_version)
        mini = parse_version(min_version)
        maxi = parse_version(max_version) if max_version else (9999, 9999, 9999)

        return mini <= curr <= maxi

    def _build_filters(self, context, engine_name):
        """Construct filters for querying Shotgun."""
        filters = [
            ['sg_status_list', 'is', 'act'],
            ['sg_exclude_projects', 'not_in', context.project],
            ['sg_exclude_users', 'not_in', context.user],
            {'filter_operator': 'any', 'filters': [
                ['sg_projects', 'in', context.project],
                ['sg_projects', 'is', None]
            ]},
            {'filter_operator': 'any', 'filters': [
                ['sg_users', 'in', context.user],
                ['sg_users', 'is', None]
            ]}
        ]

        if engine_name:
            filters.append({
                'filter_operator': 'any',
                'filters': [
                    ['sg_host_engines', 'contains', engine_name],
                    ['sg_host_engines', 'is', None]
                ]
            })
        else:
            filters.append(['sg_host_engines', 'is', None])

        return filters