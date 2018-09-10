from .StreamDeck import StreamDeck
from ruamel.yaml import YAML
import time

current_milli_time = lambda: int(round(time.time() * 1000))
time_passed = lambda since: current_milli_time() - since

class MenuManager:
    def __init__(self, streamDeck):
        self.streamDeck = streamDeck
        self.menues = dict()
        self.currentMenu = None

        for key in range(StreamDeck.KEY_COUNT):
            self.streamDeck.add_key_callback(key, self._on_key_state_changed)

    def __del__(self):
        if self.streamDeck is not None:
            for key in range(StreamDeck.KEY_COUNT):
                self.streamDeck.remove_key_callback(key, self._on_key_state_changed)

    def __setstate__(self, state):
        self.streamDeck = None
        self.__dict__.update(state)

    def __getstate__(self):
        return {"currentMenu": self.currentMenu, "menues": self.menues}

    def __eq__(self, other):
        if isinstance(other, MenuManager):
            return other.__getstate__() == self.__getstate__()
        else: return False

    def add_menu(self, id, menu):
        self.menues[id] = menu
    def _on_key_state_changed(self, key, old_state, new_state):
        if self.currentMenu is not None:
            self.currentMenu._on_key_state_changed(key, old_state,new_state)

class Menu:
    def __init__(self):
        self.buttons = dict()

    def _on_key_state_changed(self, key, old_state, new_state):
        if self.buttons[key] is not None:
            self.buttons[key]._on_key_state_changed(key,old_state,new_state)

    def open(self, streamdeck):
        """ Executed when this menu is opened """
        streamdeck.clear()

    def set_button(self, key, button):
        if not StreamDeck.is_valid_key(key): raise IndexError("Invalid key index {}.".format(key))
        self.buttons[int(key)] = button

    def __getstate__(self):
        return {"buttons": self.buttons}

    def __eq__(self, other):
        if isinstance(other, Menu):
            return other.__getstate__() == self.__getstate__()
        else: return False

class Button:
    T_LONG_PRESS = 400 # Duration a Button has to be pressed down to be considered a long press
    T_DOUBLE_CLICK = 100

    def __init__(self, icon_path=None):
        self.t_last_pressed = current_milli_time()

        self.icon_path = icon_path

        self.is_long_pressing = False
        self.is_pressed = False

        # Special Event Callbacks
        self.during_long_press_callback = None

    def _on_key_state_changed(self, key, old_state, new_state):
        if new_state == True:
            self.is_pressed = True
            self.is_long_pressing = False
            self.t_last_pressed = current_milli_time()
            self.on_pressed()
        else: 
            self.is_pressed = False
            if self.is_long_pressing:
                self.on_long_press()
                self.is_long_pressing = False
            else: self.on_released()

    def _tick(self):
        """ 
        Called to let the Button update itself (i.e. icon, etc.)
        """
        if self.during_long_press_callback is not None:
            if  self.is_pressed and time_passed(self.t_last_pressed) > self.T_LONG_PRESS: self.is_long_pressing = True
            if self.is_long_pressing: self.during_long_press_callback()

    def on_pressed(self):
        """ Called when the corresponding key on the StreamDeck was pressed """
        pass

    def on_released(self):
        """ Called when the corresponding key on the StreamDeck was released """
        pass

    def on_long_press(self):
        """ 
        Called when the corresponding key on the StreamDeck was pressed for a long time.
        If this Method isn't implemented by the child class, 'on_released' will be called instead.
        """
        self.on_released() # If this method isn't implemented by a child class, execute 'on_released' instead

    def set_during_long_press_callback(self, callback):
        self.during_long_press_callback = callback

    def __getstate__(self):
        return {"icon_path": self.icon_path}

    def __eq__(self, other):
        if isinstance(other, Button):
            return other.__getstate__() == self.__getstate__()
        else: return False