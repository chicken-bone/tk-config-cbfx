# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This hook gets executed before and after the context changes in Toolkit.
"""
import os
from tank import get_hook_baseclass

color_config_entity = "CustomNonProjectEntity06"
color_config_field = "sg_color_config"


class ContextChange(get_hook_baseclass()):
    """
    - If an engine **starts up**, the ``current_context`` passed to the hook
      methods will be ``None`` and the ``next_context`` parameter will be set
      to the context that the engine is starting in.

    - If an engine is being **reloaded**, in the context of an engine restart
      for example, the ``current_context`` and ``next_context`` will usually be
      the same.

    - If a **context switch** is requested, for example when a user switches
      from project to shot mode in Nuke Studio, ``current_context`` and ``next_context``
      will contain two different context.

    .. note::

       These hooks are called whenever the context is being set in Toolkit. It is
       possible that the new context will be the same as the old context. If
       you want to trigger some behavior only when the new one is different
       from the old one, you'll need to compare the two arguments using the
       ``!=`` operator.
    """

    def pre_context_change(self, current_context, next_context):
        """
        Executed before the context has changed.

        The default implementation does nothing.

        :param current_context: The context of the engine.
        :type current_context: :class:`~sgtk.Context`
        :param next_context: The context the engine is switching to.
        :type next_context: :class:`~sgtk.Context`
        """
        pass

    def post_context_change(self, previous_context, current_context):
        """
        Executed after the context has changed.

        The default implementation does nothing.

        :param previous_context: The previous context of the engine.
        :type previous_context: :class:`~sgtk.Context`
        :param current_context: The current context of the engine.
        :type current_context: :class:`~sgtk.Context`
        """
        if current_context != previous_context and current_context is not None:

            env_vars = {
                "SEQ": None,
                "SHOT": None,
                "LUT": None,
                "CAMERA_RAW": None,
            }

            seq_color_config = None
            shot_color_config = None
            project_color_config = None
            current_color_config = None

            # Sets the SEQ and SHOT env vars and color configs
            if current_context.entity:
                type = current_context.entity['type']
                id = current_context.entity['id']
                entity = current_context.sgtk.shotgun.find_one(type, [['id', 'is', id]], ['code', 'sg_sequence', color_config_field])
                if type == "Sequence":
                    env_vars["SEQ"] = entity.get('sg_sequence').get('name')
                    seq_color_config = entity.get(color_config_field)
                if type == "Shot":
                    seq_id = entity.get('sg_sequence').get('id')
                    env_vars["SEQ"] = entity.get('sg_sequence').get('name')
                    env_vars["SHOT"] = entity.get("code")
                    shot_color_config = entity.get(color_config_field)
                    seq_entity = current_context.sgtk.shotgun.find_one('Sequence', [['id', 'is', seq_id]], ['code', color_config_field])
                    seq_color_config = seq_entity.get(color_config_field)

            # Sets the PROJECT env var
            if current_context.project:
                id = current_context.project['id']
                entity = current_context.sgtk.shotgun.find_one('Project', [['id', 'is', id]], ['code', color_config_field])
                project_color_config = entity.get(color_config_field)

            # each color config will override the previous if one exists
            if project_color_config:
                current_color_config = project_color_config
            if seq_color_config:
                current_color_config = seq_color_config
            if shot_color_config:
                current_color_config = shot_color_config

            if current_color_config:
                color = current_context.sgtk.shotgun.find_one(color_config_entity, [['id', 'is', current_color_config['id']]], ['code', 'sg_camera_raw', 'sg_project_lut'])
                env_vars["LUT"] = color.get("sg_project_lut")

            # set the env variables for OCIO to pick up
            for key, value in env_vars.iteritems():
                if not value:
                    if os.environ.get(key):
                        self.log_debug("Clearing ENV variable: {}".format(key))
                        os.environ.pop(key)
                else:
                    self.log_debug("Setting ENV variable: {} = {}".format(key, value))
                    os.environ[key] = value
