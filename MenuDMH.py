# system imports
import gettext
import logging

# third part imports
import numpy

# local libraries
# None

_ = gettext.gettext


class MenuDMHDelegate(object):

    def __init__(self, api):
        self.__api = api
        self.menu_id = "dmh_menu"  # required, specify menu_id where this item will go
        self.menu_name = _("DMH")  # optional, specify default name if not a standard menu
        self.menu_before_id = "window_menu"  # optional, specify before menu_id if not a standard menu
        self.menu_item_name = _("DMH Menu Item")  # menu item name

    def close(self):
        # close will be called if the extension is unloaded.
        pass

    def menu_item_execute(self, document_window):
        self.__api.library.create_data_item_from_data(numpy.random.randn(64, 64), title=_("Random 64"))
        logging.info("MenuDMHDelegate menu_item_execute has been called.")


class MenuDMHExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.examples.menu_dmh"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__menu_item_ref = api.create_menu_item(MenuDMHDelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__menu_item_ref.close()
        self.__menu_item_ref = None
