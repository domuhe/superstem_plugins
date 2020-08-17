# standard libraries
import gettext
import typing

from nion.ui import Dialog, UserInterface

# third party libraries
# None

# local libraries
# None

_ = gettext.gettext


class DialogExampleDelegate:

    def __init__(self, api):
        self.__api = api
        self.panel_id = "dialog-example-panel"
        self.panel_name = _("Dialog Example")
        self.panel_positions = ["left", "right"]
        self.panel_position = "right"

        self.__action_dialog_open = False

    def show_action_dialog(self):
        class ExampleDialog(Dialog.ActionDialog):
            """
            Create a modeless dialog that always stays on top of the UI by default (can be controlled with the
            parameter 'window_style').

            Parameters:
            -----------
            ui : An instance of nion.ui.UserInterface, required.
            on_accept : callable, optional.
                This method will be called when the user clicks 'OK'
            on_reject : callable, optional.
                This method will be called when the user clicks 'Cancel' or the 'X'-button
            include_ok : bool, optional
                Whether to include the 'OK' button.
            include_cancel : bool, optional
                Whether to include the 'Cancel' button.
            window_style : str, optional
                Pass in 'dialog' here if you want the Dialog to move into the background when clicking outside
                of it. The default value 'tool' will cause it to always stay on top of Swift.
            """
            def __init__(self, ui: UserInterface, *,
                         on_accept: typing.Optional[typing.Callable[[], None]]=None,
                         on_reject: typing.Optional[typing.Callable[[], None]]=None,
                         include_ok: bool=True,
                         include_cancel: bool=True,
                         window_style: typing.Optional[str]=None):

                super().__init__(ui, window_style=window_style)

                self.on_accept = on_accept
                self.on_reject = on_reject

                def on_ok_clicked():
                    if self.on_accept:
                        self.on_accept()
                    # Return 'True' to tell Swift to close the Dialog
                    return True
                if include_ok:
                    self.add_button('OK', on_ok_clicked)

                def on_cancel_clicked():
                    if self.on_reject:
                        self.on_reject()
                    # Return 'True' to tell Swift to close the Dialog
                    return True
                if include_cancel:
                    self.add_button('Cancel', on_cancel_clicked)

                column = self.ui.create_column_widget()
                row = self.ui.create_row_widget()
                label = self.ui.create_label_widget('This is a modeless dialog.')

                row.add_spacing(10)
                row.add(label)
                row.add_spacing(10)
                row.add_stretch()

                column.add_spacing(10)
                column.add(row)
                column.add_spacing(10)
                column.add_stretch()

                self.content.add(column)

            def about_to_close(self, geometry: str, state: str) -> None:
                """
                Required to properly close the Dialog.
                """
                if self.on_reject:
                    self.on_reject()
                super().about_to_close(geometry, state)

        # We track open dialogs to ensure that only one dialog can be open at a time
        if not self.__action_dialog_open:
            self.__action_dialog_open = True
            dc = self.__api.application.document_controllers[0]._document_controller
            # This function will inform the main panel that the dialog has been closed, so that it will allow
            # opening a new one
            def report_dialog_closed():
                self.__action_dialog_open = False
            # We pass in `report_dialog_closed` so that it gets called when the dialog is closed.
            # If you want to invoke different actions when the user clicks 'OK' and 'Canclel', you can of course pass
            # in two different functions for `on_accept` and `on_reject`.
            ExampleDialog(dc.ui, on_accept=report_dialog_closed, on_reject=report_dialog_closed).show()

    def create_panel_widget(self, ui, document_controller):
        column = ui.create_column_widget()

        button_row = ui.create_row_widget()
        button_widget = ui.create_push_button_widget(_('Show example dialog'))
        button_widget.on_clicked = self.show_action_dialog

        button_row.add_spacing(8)
        button_row.add(button_widget)
        button_row.add_spacing(8)
        button_row.add_stretch()

        column.add_spacing(8)
        column.add(button_row)
        column.add_spacing(8)
        column.add_stretch()

        return column


class DialogExampleExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.examples.dialog_example"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__panel_ref = api.create_panel(DialogExampleDelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__panel_ref.close()
        self.__panel_ref = None
