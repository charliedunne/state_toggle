# -*- coding: utf-8; -*-

# Copyright (C) 2015 - 2019 Lionel Ott
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
from xml.etree import ElementTree

from PyQt5 import QtWidgets

from gremlin.base_classes import AbstractAction, AbstractFunctor
from gremlin.common import InputType
from gremlin.input_devices import ButtonReleaseActions
import gremlin.ui.common
import gremlin.ui.input_item

# Required for passing arguments in callback
from functools import partial


class StateToggleWidget(gremlin.ui.input_item.AbstractActionWidget):

    """UI widget for mapping inputs to keyboard key combinations."""

    def __init__(self, action_data, parent=None):
        """Creates a new instance.

        :param action_data the data managed by this widget
        :param parent the parent of this widget
        """

        # Create a global list of key_combinations
        self.list_key_combination = []

        super().__init__(action_data, parent=parent)


    def _update_keys(self, keys):
        """Updates the storage with a new set of keys.

        :param keys the keys to use in the key combination
        """

        # Note that self.id is populated by _record_keys_cb each time
        # the recording widget is created and hence identified by this
        # id to which of the list is referring to.
        self.action_data.chain_states[self.id] = [(key.scan_code, key.is_extended) for key in keys]
        self.action_modified.emit()

    def _record_keys_cb(self, id):
        """Prompts the user to press the desired key combination.

        :param id Index of the array of the chain_states that is handled.
        """

        # The ID parameter received is populated globaly so other callbacks
        # can be aware.
        self.id = id
        button_press_dialog = gremlin.ui.common.InputListenerWidget(
            self._update_keys,
            [InputType.Keyboard],
            return_kb_event=False,
            multi_keys=True
        )

        # Display the dialog centered in the middle of the UI
        root = self
        while root.parent():
            root = root.parent()
        geom = root.geometry()

        button_press_dialog.setGeometry(
            geom.x() + geom.width() / 2 - 150,
            geom.y() + geom.height() / 2 - 75,
            300,
            150
        )

        button_press_dialog.show()

    def _create_ui(self):
        """Creates the UI components."""

        # Presentation of the number of states
        self.states_layout = QtWidgets.QHBoxLayout()

        self.states_layout.addWidget(QtWidgets.QLabel("<b>States:</b> "))
        self.num_states = gremlin.ui.common.DynamicDoubleSpinBox()
        self.num_states.setRange(0, self.action_data.MAX_STATES)
        self.num_states.setSingleStep(1)
        self.num_states.setValue(self.action_data.num_states)
        self.num_states.valueChanged.connect(self._states_changed_cb)
        self.states_layout.addWidget(self.num_states)

        self.states_layout.addStretch(5)

        self.main_layout.addLayout(self.states_layout)

        # Creation of the action dialogs for each state
        for i in range(0, self.action_data.num_states):
            key_combination = QtWidgets.QLabel()
            button_msg = "Record State " + str(i)
            record_button = QtWidgets.QPushButton(button_msg, self)

            # Note about the use of partial to provide the ID to the callback
            # and hence identify to which of the actions is referring to.
            record_button.clicked.connect(partial(self._record_keys_cb, i))

            self.list_key_combination.append(key_combination)

            self.main_layout.addWidget(key_combination)
            self.main_layout.addWidget(record_button)
            self.main_layout.addStretch(1)


    def _populate_ui(self):
        """Populates the UI components."""

        # Index for list_key_combinations
        i = 0

        for eachkey in self.action_data.chain_states:

            text = "<b>Current keys combination:</b> "
            names = []

            for key in eachkey:
                names.append(gremlin.macro.key_from_code(*key).name)

            text += " + ".join(names)
            self.list_key_combination[i].setText(text)

            # Increase the list_key_combinations index
            i = i + 1

    def _states_changed_cb(self, value):
        """Stores changes to the states element and create the elements required
        in the chain_states array.

        :param value the new value of the states field
        """

        if (int(value) > self.action_data.num_states):
            # Append new key structure in the chain_state list
            for i in range(0, int(value) - self.action_data.num_states):
                key = []
                self.action_data.chain_states.append(key)
        else:
            # Remove not required state(s)
            for i in range(0, self.action_data.num_states - int(value)):
                self.action_data.chain_states.pop()

        self.action_data.num_states = int(value)
        self.action_modified.emit()


class StateToggleFunctor(AbstractFunctor):

    def __init__(self, action):
        super().__init__(action)

        # Creation of lists of the shared variables
        self.press = []
        self.needs_auto_release = []
        self.release = []

        # This variable shall define the key that has to be pressed in each press
        self.num_states = action.num_states
        self.current_toggle = 0

        # Parse all the actions and fill the shared variables
        for i in range(0, action.num_states):

            press = gremlin.macro.Macro()
            needs_auto_release = True
            for key in action.chain_states[i]:
                press.press(gremlin.macro.key_from_code(key[0], key[1]))

            release = gremlin.macro.Macro()
            for key in action.chain_states[i]:
                release.release(gremlin.macro.key_from_code(key[0], key[1]))

            self.press.append(press)
            self.needs_auto_release.append(needs_auto_release)
            self.release.append(release)

    def process_event(self, event, value):
        if value.current:

            # Note that each time this callback is awaken it must be treated as a single
            # action that act over the self.current_toggle action.

            gremlin.macro.MacroManager().queue_macro(self.press[self.current_toggle])

            if self.needs_auto_release[self.current_toggle]:
                ButtonReleaseActions().register_callback(
                    lambda: gremlin.macro.MacroManager().queue_macro(self.release[self.current_toggle]),
                    event
                )

        else:
            gremlin.macro.MacroManager().queue_macro(self.release[self.current_toggle])

            # Increment the index of the next key to press
            self.current_toggle = (self.current_toggle + 1) % self.num_states

        return True


class StateToggle(AbstractAction):

    """Action data for the map to keyboard action.

    Map to keyboard presses and releases a set of keys in sync with another
    physical input being pressed or released.
    """

    name = "State Toggle"
    tag = "StateToggle"
    subtag = "state"

    default_button_activation = (True, True)
    input_types = [
        InputType.JoystickAxis,
        InputType.JoystickButton,
        InputType.JoystickHat,
        InputType.Keyboard
    ]

    functor = StateToggleFunctor
    widget = StateToggleWidget

    def __init__(self, parent):
        """Creates a new instance.

        :param parent the container this action is part of
        """
        super().__init__(parent)

        # Creation of the global parameters that contain the list of states
        self.chain_states = []

        # Variable that manage the number of states available
        self.num_states = 0

        # Maximum states (CONSTANT)
        self.MAX_STATES = 10

    def icon(self):
        """Returns the icon to use for this action.

        :return icon representing this action
        """
        return "{}/icon.png".format(os.path.dirname(os.path.realpath(__file__)))

    def requires_virtual_button(self):
        """Returns whether or not an activation condition is needed.

        :return True if an activation condition is required for this particular
            action instance, False otherwise
        """
        return self.get_input_type() in [
            InputType.JoystickAxis,
            InputType.JoystickHat
        ]

    def _parse_xml(self, node):
        """Reads the contents of an XML node to populate this instance.

        :param node the node whose content should be used to populate this
            instance
        """
        # Each action shall be encapsulated into a <state> tag, and inside <state>
        # there shall be each one of the <key> required for the action.

        for state in node.findall(self.subtag):

            keys = []

            for child in state.findall("key"):
                keys.append((
                    int(child.get("scan-code")),
                    gremlin.profile.parse_bool(child.get("extended"))
                ))

            self.chain_states.append(keys)
            self.num_states = self.num_states + 1

    def _generate_xml(self):
        """Returns an XML node containing this instance's information.

        :return XML node containing the information of this  instance
        """

        # Each action shall be encapsulated into a <state> tag, and inside <state>
        # there shall be each one of the <key> required for the action.

        node = ElementTree.Element(self.tag)
        for eachkey in self.chain_states:
            state_node = ElementTree.Element(self.subtag)
            for key in eachkey:
                key_node = ElementTree.Element("key")
                key_node.set("scan-code", str(key[0]))
                key_node.set("extended", str(key[1]))
                state_node.append(key_node)
            node.append(state_node)
        return node

    def _is_valid(self):
        """Returns whether or not this action is valid.

        :return True if the action is configured correctly, False otherwise
        """
        return len(self.chain_states) > 0


version = 1
name = "State Toggle"
create = StateToggle
