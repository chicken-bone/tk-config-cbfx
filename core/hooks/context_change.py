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

import base64
import os
import pickle

import sgtk
from sgtk import get_hook_baseclass

try:
    import vfxjob

    vfxjob_loaded = True
except ModuleNotFoundError:
    vfxjob_loaded = False


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

    __field_folder_name = "tank_name"
    __field_camera_raw = "sg_camera_raw"
    __field_lut = "sg_lut"
    __field_fps = "sg_frame_rate"
    __field_cut_in = "sg_cut_in"
    __field_cut_out = "sg_cut_out"
    __field_head_in = "sg_head_in"
    __field_tail_out = "sg_tail_out"

    __shot_fields = [
        "code",
        "sg_sequence",
        __field_camera_raw,
        __field_lut,
        __field_cut_in,
        __field_cut_out,
        __field_head_in,
        __field_tail_out,
    ]
    __sequence_fields = ["code", __field_camera_raw, __field_lut]
    __project_fields = [
        "code",
        __field_camera_raw,
        __field_lut,
        __field_folder_name,
        __field_fps,
    ]
    __task_fields = ["code", "entity"]

    def pre_context_change(self, current_context, next_context):
        """
        Executed before the context has changed.

        The default implementation does nothing.

        :param current_context: The context of the engine.
        :type current_context: :class:`~sgtk.Context`
        :param next_context: The context the engine is switching to.
        :type next_context: :class:`~sgtk.Context`
        """
        self.current_context = current_context
        self.next_context = next_context

        self.shot_entity = None
        self.sequence_entity = None
        self.asset_entity = None
        self.project_entity = None

        if next_context != current_context and next_context is not None:
            # if next_context.project is none we can assume we are in a 'site' context and
            # we should not fire
            if next_context.project is None:
                return

            self.env_vars = {
                "SHOTGUN_CONTEXT_ID": None,
                "SHOTGUN_CONTEXT_TYPE": None,
                "SHOTGUN_TASK_ID": None,
                "SHOTGUN_PROJECT_ID": None,
                "SHOTGUN_PROJECT_CODE": None,
                "SHOTGUN_SHOT_ID": None,
                "SHOTGUN_SHOT_CODE": None,
                "SHOTGUN_SEQUENCE_ID": None,
                "SHOTGUN_SEQUENCE_CODE": None,
                "SHOTGUN_ASSET_ID": None,
                "SHOTGUN_ASSET_CODE": None,
                "SHOTGUN_EDIT_CUT_IN": None,
                "SHOTGUN_EDIT_CUT_OUT": None,
                "SHOTGUN_EDIT_HEAD_IN": None,
                "SHOTGUN_EDIT_TAIL_OUT": None,
                "SHOTGUN_FPS": None,
                "SHOT": None,  # redundant but needed for OCIO context
                "SEQ": None,  # redundant but needed for OCIO context
            }

            if next_context.task:
                self.env_vars["SHOTGUN_TASK_ID"] = next_context.task["id"]
                self.env_vars["SHOTGUN_CONTEXT_ID"] = next_context.task["id"]
                self.env_vars["SHOTGUN_CONTEXT_TYPE"] = next_context.task["type"]

            if next_context.entity:
                self.entity_type = next_context.entity["type"]
                self.entity_id = next_context.entity["id"]

                self.env_vars["SHOTGUN_ENTITY_ID"] = self.entity_id
                self.env_vars["SHOTGUN_ENTITY_TYPE"] = self.entity_type

                if not next_context.task:
                    self.env_vars["SHOTGUN_CONTEXT_ID"] = self.entity_id
                    self.env_vars["SHOTGUN_CONTEXT_TYPE"] = self.entity_type

            elif next_context.project:
                # self.handle_project(next_context)

                self.entity_type = "Project"
                self.entity_id = next_context.project["id"]

                if not next_context.task:
                    self.env_vars["SHOTGUN_CONTEXT_ID"] = self.entity_id
                    self.env_vars["SHOTGUN_CONTEXT_TYPE"] = self.entity_type

            # commits required context to an encoded SHOTGUN_BOOTSTRAP_CACHE env var
            self.create_bootstrap_cache(next_context)

            self.build_environs(self.entity_type)

            # setting job details for setting proper job environment
            if vfxjob_loaded:
                vfxjob.utils.prep_environment_for_rez(
                    self.project_entity.get(self.__field_folder_name)
                )

    def build_environs(self, context_type):
        if context_type == "Shot":
            self.shot_entity = self.next_context.sgtk.shotgun.find_one(
                "Shot", [["id", "is", self.entity_id]], self.__shot_fields
            )

            self.env_vars["SHOTGUN_SHOT_CODE"] = self.env_vars["SHOT"] = (
                self.shot_entity.get("code")
            )
            self.env_vars["SHOTGUN_SHOT_ID"] = self.shot_entity.get("id")
            self.env_vars["SHTOGUN_EDIT_CUT_IN"] = self.shot_entity.get(
                self.__field_cut_in
            )
            self.env_vars["SHTOGUN_EDIT_CUT_OUT"] = self.shot_entity.get(
                self.__field_cut_out
            )
            self.env_vars["SHTOGUN_EDIT_HEAD_IN"] = self.shot_entity.get(
                self.__field_head_in
            )
            self.env_vars["SHTOGUN_EDIT_TAIL_OUT"] = self.shot_entity.get(
                self.__field_tail_out
            )

            shot_sequence = self.shot_entity.get("sg_sequence")
            if shot_sequence:
                sequence_id = self.shot_entity.get("sg_sequence").get("id")
                self.sequence_entity = self.next_context.sgtk.shotgun.find_one(
                    "Sequence", [["id", "is", sequence_id]], self.__sequence_fields
                )
                self.env_vars["SHOTGUN_SEQUENCE_CODE"] = self.env_vars["SEQ"] = (
                    self.sequence_entity.get("code")
                )
                self.env_vars["SHOTGUN_SEQUENCE_ID"] = self.sequence_entity.get("id")

            self.project_entity = self.next_context.sgtk.shotgun.find_one(
                "Project",
                [["id", "is", self.next_context.project["id"]]],
                self.__project_fields,
            )
            self.env_vars["SHOTGUN_PROJECT_CODE"] = self.project_entity.get("code")
            self.env_vars["SHOTGUN_PROJECT_ID"] = self.project_entity.get("id")
            self.env_vars["SHOTGUN_FPS"] = self.project_entity.get(self.__field_fps)

        if context_type == "Sequence":
            self.sequence_entity = self.next_context.sgtk.shotgun.find_one(
                "Sequence", [["id", "is", self.entity_id]], self.__sequence_fields
            )
            self.env_vars["SHOTGUN_SEQUENCE_CODE"] = self.env_vars["SEQ"] = (
                self.sequence_entity.get("code")
            )
            self.env_vars["SHOTGUN_SEQUENCE_ID"] = self.sequence_entity.get("id")

        if context_type == "Asset":
            self.asset_entity = self.next_context.sgtk.shotgun.find_one(
                "Asset", [["id", "is", self.entity_id]], self.__asset_fields
            )
            self.env_vars["SHOTGUN_ASSET_CODE"] = self.asset_entity.get("code")
            self.env_vars["SHOTGUN_ASSET_ID"] = self.asset_entity.get("id")

        self.project_entity = self.next_context.sgtk.shotgun.find_one(
            "Project",
            [["id", "is", self.next_context.project["id"]]],
            self.__project_fields,
        )
        self.env_vars["SHOTGUN_PROJECT_CODE"] = self.project_entity.get("code")
        self.env_vars["SHOTGUN_PROJECT_ID"] = self.project_entity.get("id")
        self.env_vars["SHOTGUN_FPS"] = self.project_entity.get(self.__field_fps)

        # set the env variables
        for key, value in self.env_vars.items():
            if not value:
                if os.environ.get(key):
                    self.logger.debug("Clearing ENV variable: {}".format(key))
                    os.environ.pop(key)
            else:
                self.logger.debug("Setting ENV variable: {} = {}".format(key, value))
                os.environ[key] = str(value)

    def create_bootstrap_cache(self, next_context):
        def encode_object(obj):
            return base64.b64encode(pickle.dumps(obj)).decode("utf-8")

        cached_vars = {
            "SHOTGUN_SITE": None,
            "SHOTGUN_CONFIG_URI": None,
            "SHOTGUN_SGTK_MODULE_PATH": None,
            "SHOTGUN_ENGINE_NAME": None,
            "SHOTGUN_CONTEXT_ID": None,
            "SHOTGUN_CONTEXT_TYPE": None,
            "SHOTGUN_PROJECT_ID": None,  # needed for fallback if filesystem sync needs to be run
        }

        cached_vars["SHOTGUN_SITE"] = os.getenv("SHOTGUN_SITE")
        cached_vars["SHOTGUN_CONFIG_URI"] = (
            next_context.sgtk.configuration_descriptor.get_uri()
        )
        cached_vars["SHOTGUN_SGTK_MODULE_PATH"] = os.path.join(
            os.environ["SHOTGUN_BUNDLE_CACHE_PATH"],
            "app_store",
            "tk-core",
            next_context.sgtk.version,
            "python",
        )

        engine = sgtk.platform.current_engine()
        if engine:
            cached_vars["SHOTGUN_ENGINE_NAME"] = engine.name

        if next_context.task:
            cached_vars["SHOTGUN_CONTEXT_ID"] = next_context.task["id"]
            cached_vars["SHOTGUN_CONTEXT_TYPE"] = next_context.task["type"]
        elif hasattr(self, "entity_id"):
            cached_vars["SHOTGUN_CONTEXT_ID"] = self.entity_id
            cached_vars["SHOTGUN_CONTEXT_TYPE"] = self.entity_type

        if next_context.project:
            cached_vars["SHOTGUN_PROJECT_ID"] = next_context.project["id"]

        self.env_vars["SHOTGUN_BOOTSTRAP_CACHE"] = encode_object(cached_vars)
        self.env_vars["SHOTGUN_USER_CACHE"] = sgtk.authentication.serialize_user(
            sgtk.get_authenticated_user(), use_json=False
        )

    def post_context_change(self, previous_context, current_context):
        """
        Executed after the context has changed.

        The default implementation does nothing.

        :param previous_context: The previous context of the engine.
        :type previous_context: :class:`~sgtk.Context`
        :param current_context: The current context of the engine.
        :type current_context: :class:`~sgtk.Context`
        """
        pass