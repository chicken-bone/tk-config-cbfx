# Copyright notice preserved...

"""
This hook gets executed before and after the context changes in Toolkit.
"""
import os
from tank import get_hook_baseclass


class ContextChange(get_hook_baseclass()):
    """
    Original docstring preserved...
    """

    __field_camera_raw = "sg_camera_raw"
    __field_lut = "sg_lut"
    __field_cut_in = "sg_cut_in"
    __field_cut_out = "sg_cut_out"
    __field_head_in = "sg_head_in"
    __field_tail_out = "sg_tail_out"

    __shot_fields = ['code', 'sg_sequence', __field_camera_raw,
                     __field_lut, __field_cut_in, __field_cut_out,
                     __field_head_in, __field_tail_out]
    __seq_fields = ['code', __field_camera_raw, __field_lut]
    __show_fields = ['code', __field_camera_raw, __field_lut]

    def pre_context_change(self, current_context, next_context):
        """
        Original docstring preserved...
        """

        if next_context != current_context and next_context is not None:

            env_vars = {
                "SHOW": None,
                "SEQ": None,
                "SHOT": None,
                "LUT": "default.cube",
                "CAMERA_RAW": None,
                "EDIT_CUT_IN": None,
                "EDIT_CUT_OUT": None,
                "EDIT_HEAD_IN": None,
                "EDIT_TAIL_OUT": None,
            }

            if next_context.entity:
                self.logger.debug("Switching Context: {}".format(next_context))
                type_ = next_context.entity['type']  # Changed 'type' to 'type_' as it's a built-in
                id_ = next_context.entity['id']      # Changed 'id' to 'id_' as it's a built-in
                if type_ == "Shot":
                    shot_entity = next_context.sgtk.shotgun.find_one(type_, [['id', 'is', id_]], self.__shot_fields)
                    shot_code = shot_entity.get('code')

                    seq_id = shot_entity.get('sg_sequence').get('id')
                    seq_entity = next_context.sgtk.shotgun.find_one('Sequence', [['id', 'is', seq_id]], self.__seq_fields)
                    seq_code = seq_entity.get('code')

                    show_id = next_context.project['id']
                    show_entity = next_context.sgtk.shotgun.find_one('Project', [['id', 'is', show_id]], self.__show_fields)
                    show_code = show_entity.get('code')

                    shot_camera_raw, shot_lut = shot_entity.get(self.__field_camera_raw), shot_entity.get(self.__field_lut)
                    seq_camera_raw, seq_lut = seq_entity.get(self.__field_camera_raw), seq_entity.get(self.__field_lut)
                    show_camera_raw, show_lut = show_entity.get(self.__field_camera_raw), show_entity.get(self.__field_lut)

                    env_vars["SHOW"] = show_code
                    env_vars["SEQ"] = seq_code
                    env_vars["SHOT"] = shot_code

                    env_vars["EDIT_CUT_IN"] = shot_entity.get(self.__field_cut_in)
                    env_vars["EDIT_CUT_OUT"] = shot_entity.get(self.__field_cut_out)
                    env_vars["EDIT_HEAD_IN"] = shot_entity.get(self.__field_head_in)
                    env_vars["EDIT_TAIL_OUT"] = shot_entity.get(self.__field_tail_out)

                    if shot_camera_raw:
                        env_vars["CAMERA_RAW"] = shot_camera_raw
                    elif seq_camera_raw:
                        env_vars["CAMERA_RAW"] = seq_camera_raw
                    elif show_camera_raw:
                        env_vars["CAMERA_RAW"] = show_camera_raw

                    if shot_lut:
                        env_vars["LUT"] = shot_lut
                    elif seq_lut:
                        env_vars["LUT"] = seq_lut
                    elif show_lut:
                        env_vars["LUT"] = show_lut

                if type_ == "Sequence":
                    seq_entity = next_context.sgtk.shotgun.find_one(type_, [['id', 'is', id_]], self.__seq_fields)
                    seq_code = seq_entity.get('code')

                    show_id = next_context.project['id']
                    show_entity = next_context.sgtk.shotgun.find_one('Project', [['id', 'is', show_id]], self.__show_fields)
                    show_code = show_entity.get('code')

                    seq_camera_raw, seq_lut = seq_entity.get(self.__field_camera_raw), seq_entity.get(self.__field_lut)
                    show_camera_raw, show_lut = show_entity.get(self.__field_camera_raw), show_entity.get(self.__field_lut)

                    env_vars["SHOW"] = show_code
                    env_vars["SEQ"] = seq_code

                    if seq_camera_raw:
                        env_vars["CAMERA_RAW"] = seq_camera_raw
                    elif show_camera_raw:
                        env_vars["CAMERA_RAW"] = show_camera_raw

                    if seq_lut:
                        env_vars["LUT"] = seq_lut
                    elif show_lut:
                        env_vars["LUT"] = show_lut

            elif next_context.project:
                show_id = next_context.project['id']
                show_entity = next_context.sgtk.shotgun.find_one('Project', [['id', 'is', show_id]], self.__show_fields)
                show_code = show_entity.get('code')
                show_camera_raw, show_lut = show_entity.get(self.__field_camera_raw), show_entity.get(self.__field_lut)
                env_vars["SHOW"] = show_code
                if show_camera_raw:
                    env_vars["CAMERA_RAW"] = show_camera_raw
                if show_lut:
                    env_vars["LUT"] = show_lut

            # set the env variables for OCIO to pick up
            for key, value in list(env_vars.items()):  # Changed iteritems() to items()
                if not value:
                    if os.environ.get(key):
                        self.logger.debug("Clearing ENV variable: {}".format(key))
                        os.environ.pop(key)
                else:
                    self.logger.debug("Setting ENV variable: {} = {}".format(key, value))
                    os.environ[key] = str(value)

    def post_context_change(self, previous_context, current_context):
        """
        Original docstring preserved...
        """
        pass