# standard libraries
import gettext
import logging
import datetime
import os
import pathlib
import functools
import typing
import json

# local libraries
from nion.ui import Dialog, UserInterface
from nion.swift.model import ImportExportManager
from nion.swift.model import Cache

_ = gettext.gettext


# utility functions
def divide_round_up(x, n):
    """ returns integer division rounded up """
    return int((x + (n - 1))/n)


# functions to handle prefix and postfix strings for renaming
def get_prefix_string(no_field_string):
    """ constructs the prefix string for the renamed display item """
    # pad No with leading zeros
    prefix_string = str(no_field_string.zfill(3)) + "_"
    return prefix_string


def get_postfix_string(sub_field_string, fov_field_string, descr_field_string):
    """  constructs the postfix string for the renamed display item """
    if str(sub_field_string) == "":
        postfix_string = ("_" + str(fov_field_string) + "nm_"
                              + str(descr_field_string))
    else:
        postfix_string = ("_" + str(sub_field_string) + "_"
                              + str(fov_field_string) + "nm_"
                              + str(descr_field_string))
    return postfix_string


def get_superstem_settings(superstem_config_file: pathlib.Path):
    """
    Reads superstem config file and returns availabe settings dictionary
    """
    conf_file = superstem_config_file
    superstem_settings = {}
    #logging.info("Reading SuperSTEM config file %s", conf_file)

    try:  # do nothing unless config file exists and is not empty
        if conf_file.is_file() and conf_file.stat().st_size != 0:
            with open(conf_file, "r") as f:
                superstem_settings = json.load(f)
                if superstem_settings == {}:
                    logging.info("WARNING - SuperSTEM config file %s empty", conf_file)
                    logging.info("        - Please edit and enter key/value pair for export_base_directory")
                else:
                    pass
                    logging.info("- SuperSTEM settings are %s", superstem_settings)
        else:
            logging.info("WARNING - SuperSTEM config file %s NOT FOUND", conf_file)
            logging.info("        - Please create and enter key/value pair for export_base_directory")
    except Exception as e:
        logging.info("- Exception get_superstem_settings %s", e)

    return superstem_settings

def get_data_base_dir(superstem_config_file):
    """
    reads location for data base directory from superstem config file,
    if there is no entry it falls back to /tmp/NewData/sstem
    """
    data_base_dir = get_superstem_settings(superstem_config_file).get('data_base_directory')
    if data_base_dir is None:
        data_base_dir_path = pathlib.Path('/tmp/NewData/sstem/')
    else:
        data_base_dir_path = pathlib.Path(data_base_dir)

    return str(data_base_dir_path)

def get_data_base_dir_with_year(superstem_config_file):
    data_base_dir_path = pathlib.Path(get_data_base_dir(superstem_config_file))
    #we no longer want year in our data base dir path:
    #return str(data_base_dir_path.joinpath(str(datetime.datetime.now().year)))
    return str(data_base_dir_path)

def get_export_base_dir(superstem_config_file):
    """
    reads location for export base directory from superstem config file,
    if there is no entry it falls back to /tmp/NewData/sstem
    """
    export_base_dir = get_superstem_settings(superstem_config_file).get('export_base_directory')
    if export_base_dir is None:
        export_base_dir_path = pathlib.Path('/tmp/NewData/sstem/')
    else:
        export_base_dir_path = pathlib.Path(export_base_dir)

    return str(export_base_dir_path)

def get_export_base_dir_with_year(superstem_config_file):
    export_base_dir_path = pathlib.Path(get_export_base_dir(superstem_config_file))
    #we no longer want year in our export base dir path:
    #return str(export_base_dir_path.joinpath(str(datetime.datetime.now().year)))
    return str(export_base_dir_path)

def write_superstem_config_file(superstem_config_file: pathlib.Path, superstem_settings):
    """ writes the current superstem settings to the superstem config file """
    conf_file = superstem_config_file

    try:
        if conf_file.is_file():
            with open(conf_file, "w") as f:
                logging.info("UPDATING SuperSTEM config file %s", conf_file)
                json.dump(superstem_settings, f, indent=4)
        else:
            logging.info("WARNING - SuperSTEM config file NOT FOUND")
    except Exception as e:
         logging.info("- Exception write_superstem_config_file %s", e)


class PanelSuperSTEMDelegate:
    """
    This panel plugin pull together SuperSTEM modifiactions:
    - Initialisation of a new swift library based on session fields
    - It allows to set the persistent export directory from the
    session metadata and then to rename and export as DM file a display item
    based on four editable fields
    -
    Note: If you keep the Nionswift Library open overnight and then export the
    files, the default will be that the date of the export directory will not
    match the date of the Library. In this case one should manually change the
    date in the Export Dir field.
    ==========================================================================
    Revisions:

    20221028; DMH:
        Different directories for library (data_base_directory) and export 
        (export_base_directory).
        No longer have YYYY subfolder below data_base_directory and 
        export_base_directory (currently a quick hack that only comments out the
        addition of _YYYY in the functions get_data_base_dir_with_year and
        get_export_base_dir_with_year, but leave all dependend code in place.
        Removed subsubfolder (and _DMdata postfix thereof) from export directory path.
        Added fall-back to superstem_custom.json settings for site and instrument
        fields in New Liberary dialog. This uses any existing Session fields for
        site and instrument as default, then the values from superstem_custom.json.
        Corrected widget layout for Set Export Folder.
        
    20200915; DMH:
        automatic upper case for microscopist TLA
    20200911; DMH:
        finished implementing Initialise New Library Dialog,
        added background colour and enforced white background for editable fields
        tested works ok on Windows _and_ Linux
    20200826; DMH:
        added width property to widgets
    20200825; DMH:
        added Initialise New Library button and minimal functionality
    20200821; DMH:
        added SuperSTEM's own JSON config file, reading/writing thereof
    20200818; DMH:
        adjusted style closer to pep8
        adding pop up warning dialog in case filename already exists
        fine-tuned button layout with stretching
    20200817; DMH:
        implementing pathlib for OS indepedent directory and file manipulations
        enabling & disabling export buttons based on re-editing editable fields
    20200811; DMH:
        initial version
    """

    def __init__(self, api):
        self.__api = api
        self.panel_id = "superstem-panel"
        self.panel_name = _("SuperSTEM")
        self.panel_positions = ["left", "right"]
        self.panel_position = "right"
        self.api = api

        self.__warning_dialog_open = False
        self.__library_dialog_open = False

        # initial edit status of editable rename fields
        self.have_no = False
        self.have_sub = False
        self.have_fov = False
        self.have_descr = False
        self.all_good = False
        # keep track of export buttons here
        self.button_widgets_list = []
        # get current year
        self.year = datetime.datetime.now().year

        # we only export to DM
        self.io_handler_id = "dm-io-handler"

        # SuperSTEM config file
        self.superstem_config_file = api.application.configuration_location / pathlib.Path("superstem_customisation.json")
        logging.info("Using %s for SuperSTEM customisations", self.superstem_config_file)


    def show_library_dialog(self, title_string, have_ok=True, have_cancel=True):

        api = self.api
        myapi = self.__api
        superstem_config_file = self.superstem_config_file
        # this puts function in the scope of the class LibraryDialog;  - not necessary
        #get_data_base_dir_with_year_fn = get_data_base_dir_with_year(superstem_config_file)

        class LibraryDialog(Dialog.ActionDialog):
            """
            Create a modeless dialog that always stays on top of the UI
            by default (can be controlled with the parameter 'window_style').

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
                        include_ok: bool=have_ok,
                        include_cancel: bool=have_cancel,
                        window_style: typing.Optional[str]=None):

                super().__init__(ui, window_style=window_style)

                # initial edit status of editable fields
                self.have_task = False
                self.have_microscopist = False
                self.have_sample = False
                self.have_sample_area = False
                self.all_good = False

                self.on_accept = on_accept
                self.on_reject = on_reject

                self.library_name = ""
                self.data_base_dir_with_year = get_data_base_dir_with_year(superstem_config_file)

                # initialise dictionary of all session field widgets
                field_line_edit_widget_map = dict()

                # ==== main column widget ====
                column = self.ui.create_column_widget()

                # === session header row ===
                session_header_row = self.ui.create_row_widget()
                session_header_row.add_spacing(13)
                session_header_row.add(self.ui.create_label_widget(_("Session metadata for new library:")))
                session_header_row.add_stretch()

                # === session metadata entry fields widget ===
                field_descriptions = [
                    [_("Site"), _("SuperSTEM"), "site"],
                    [_("Instrument"), _("sstem3"), "instrument"],
                    [_("Task"), _("Project Number (optional)"), "task"],
                    [_("Microscopist"), _("Microscopist <TLA>"), "microscopist"],
                    [_("Sample"), _("Sample Number <Snnnn>"), "sample"],
                    [_("Sample Area"), _("Sample Description"), "sample_area"],
                ]

                def get_library_name():
                    """
                    Constructs the new library name and library index based on
                    data_base_directory in superstem config file and
                    session metadata fields in new library dialog
                    """
                    # construct new library base name and index
                    library_base_name = "_".join([
                        datetime.datetime.now().strftime("%Y_%m_%d"),
                        field_line_edit_widget_map["microscopist"].text.upper(),
                        field_line_edit_widget_map["sample"].text,
                        field_line_edit_widget_map["sample_area"].text.replace(" ","_")
                        ])

                    library_base_index = 0
                    library_base_index_str = ""
                    while os.path.exists(os.path.join(
                                            self.data_base_dir_with_year,
                                            library_base_name + library_base_index_str)):
                        library_base_index += 1
                        library_base_index_str = " " + str(library_base_index)

                    library_name = library_base_name + library_base_index_str
                    return library_name

                # == function to run on each field being changed
                def line_edit_changed(line_edit_widget, field_id, text):
                    """
                    updates the global session metadata with the field values,
                    constructs the new library name and library index and
                    updates library name field widget when all mandatory fields are filled
                    """
                    # update global session metadata with field values
                    session_metadata_key = "stem.session." + str(field_id)
                    api.library.set_library_value(session_metadata_key, text)
                    # get library name from current session fields in new library dialog
                    library_name = get_library_name()

                    # testing which fields are filled currently
                    if 'task' == field_id and text != "":
                        self.have_task = True
                    elif 'task' == field_id and text == "":
                        self.have_task = False
                    if 'microscopist' == field_id and text != "":
                        self.have_microscopist = True
                    elif 'microscopist' == field_id and text == "":
                        self.have_microscopist = False
                    if 'sample' == field_id and text != "":
                        self.have_sample = True
                    elif 'sample' == field_id and text == "":
                        self.have_sample = False
                    if 'sample_area' == field_id and text != "":
                        self.have_sample_area = True
                    elif 'sample_area' == field_id and text == "":
                        self.have_sample_area = False

                    #task is optional
                    #if self.have_task and self.have_microscopist and self.have_sample and self.have_sample_area:
                    if self.have_microscopist and self.have_sample and self.have_sample_area:
                        self.all_good = True
                    else:
                        self.all_good = False

                    def update_library_name_field():
                       """ updates the library name field if all mandatory fields are filled
                       """
                       if self.all_good:
                           library_name_field.text = library_name.replace(" ", "_")  # replace whitespace

                    myapi.queue_task(update_library_name_field)
                    line_edit_widget.request_refocus()

                # == actual widget which contains line_edit_widgets for each field
                session_data_widget = self.ui.create_column_widget()
                session_data_widget.add_spacing(8)
                # loop through all fields:
                for field_description in field_descriptions:
                    title, placeholder, field_id = field_description
                    row = self.ui.create_row_widget()
                    row.add_spacing(8)
                    row.add(self.ui.create_label_widget(title, properties={"width": 100}))
                    line_edit_widget = self.ui.create_line_edit_widget(properties={"width": 200})
                    line_edit_widget.placeholder_text = placeholder
                    # Provide default field entries for "Site" and "Instrument"
                    # take site and instrument from persistent nion settings,i.e. entries in "Session" panel
                    # if there are none, fall-back to SuperSTEM custom settings file
                    if field_id == "site" :
                        line_edit_widget.text =  myapi.library.get_library_value("stem.session.site")
                        if line_edit_widget.text ==  "":
                             line_edit_widget.text = get_superstem_settings(superstem_config_file).get('superstem_site')
                    elif field_id == "instrument":
                        line_edit_widget.text = myapi.library.get_library_value("stem.session.instrument")
                        if line_edit_widget.text ==  "":
                             line_edit_widget.text = get_superstem_settings(superstem_config_file).get('superstem_instrument')
                    # call function when field is edited:
                    line_edit_widget.on_editing_finished = functools.partial(line_edit_changed, line_edit_widget, field_id)
                    # add new widget to dictionary of widgets
                    field_line_edit_widget_map[field_id] = line_edit_widget
                    row.add(line_edit_widget)
                    session_data_widget.add(row)
                    session_data_widget.add_spacing(4)
                session_data_widget.add_stretch()

                # === Show Library Name row ===
                show_lib_name_row = self.ui.create_row_widget()
                show_lib_name_row.add_spacing(13)
                library_name_label = self.ui.create_label_widget("Library Name: ")
                library_name_field = self.ui.create_line_edit_widget(properties={"width": 300, "stylesheet": "font: italic; color: gray"})
                library_name_field.editable = False
                library_name_field.placeholder_text = "click here"
                show_lib_name_row.add(library_name_label)
                show_lib_name_row.add_spacing(26)
                show_lib_name_row.add(library_name_field)
                show_lib_name_row.add_stretch()
                show_lib_name_row.add_spacing(13)

                # === Show Data Base Folder row ===
                show_data_base_dir_row = self.ui.create_row_widget()
                show_data_base_dir_row.add_spacing(13)
                show_data_base_dir_row.add(self.ui.create_label_widget(_("Library Base Folder: "), properties={"font": "bold"}))
                show_data_base_dir_row.add_spacing(5)
                show_data_base_dir_row.add(self.ui.create_label_widget(self.data_base_dir_with_year,properties={"stylesheet": "font: italic; color: gray"}))
                show_data_base_dir_row.add_stretch()
                show_data_base_dir_row.add_spacing(13)

               # === Ok Cancel row re-purposed for Create New Library ===
                ok_cancel_row = self.ui.create_row_widget()
                ok_cancel_row.add_spacing(10)

                def handle_new():
                    if library_name_field.text != "":
                        # to ensure the application does not close upon closing the last window, force it
                        # to stay open while the window is closed and another reopened.
                        with myapi.application._application.prevent_close():
                            workspace_dir = os.path.join(self.data_base_dir_with_year, library_name_field.text)
                            Cache.db_make_directory_if_needed(workspace_dir)
                            path = os.path.join(workspace_dir, "Nion Swift Workspace.nslib")
                            if not os.path.exists(path):
                                with open(path, "w") as fp:
                                    json.dump({}, fp)
                            if os.path.exists(path):
                                myapi.application._application.create_project_reference(pathlib.Path(workspace_dir), library_name_field.text)
                                return True
                            return False

                    else:
                        logging.info("----missing field for library name!!!")

                # def handle_new_and_close():
                #     handle_new()
                #     self.request_close()
                #     return False

                def on_cancel_clicked():
                    if self.on_reject:
                        self.on_reject()
                    # Return 'True' to tell Swift to close the Dialog
                    return True

                if include_cancel:
                    self.add_button('Cancel', on_cancel_clicked)
                    ok_cancel_row.add_stretch()

                if include_ok:
                    self.add_button(_("Create New Library"), handle_new)


                # ==== Adding rows to main column ====
                column.add_spacing(12)
                column.add(session_header_row)
                column.add(session_data_widget)
                column.add_spacing(8)
                column.add(show_data_base_dir_row)
                column.add_spacing(8)
                column.add(show_lib_name_row)
                column.add_spacing(12)
                column.add(ok_cancel_row)
                column.add_spacing(8)
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
        if not self.__library_dialog_open:
            self.__library_dialog_open = True
            dc = self.__api.application.document_controllers[0]._document_controller
            # This function will inform the main panel that the dialog has been closed, so that it will allow
            # opening a new one
            def report_dialog_closed():
                self.__library_dialog_open = False
            # We pass in `report_dialog_closed` so that it gets called when the dialog is closed.
            # If you want to invoke different actions when the user clicks 'OK' and 'Canclel', you can of course pass
            # in two different functions for `on_accept` and `on_reject`.
            LibraryDialog(dc.ui, on_accept=report_dialog_closed, on_reject=report_dialog_closed).show()


    def show_warning_dialog(self, title_string, have_ok=True, have_cancel=True):
        class WarningDialog(Dialog.ActionDialog):
            """
            Create a modeless dialog that always stays on top of the UI
            by default (can be controlled with the parameter 'window_style').

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
                         include_ok: bool=have_ok,
                         include_cancel: bool=have_cancel,
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
                label = self.ui.create_label_widget(title_string)

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
        if not self.__warning_dialog_open:
            self.__warning_dialog_open = True
            dc = self.__api.application.document_controllers[0]._document_controller
            # This function will inform the main panel that the dialog has been closed, so that it will allow
            # opening a new one
            def report_dialog_closed():
                self.__warning_dialog_open = False
            # We pass in `report_dialog_closed` so that it gets called when the dialog is closed.
            # If you want to invoke different actions when the user clicks 'OK' and 'Canclel', you can of course pass
            # in two different functions for `on_accept` and `on_reject`.
            WarningDialog(dc.ui, on_accept=report_dialog_closed, on_reject=report_dialog_closed).show()

    def close(self):
        self.button_widgets_list = []

    def create_panel_widget(self, ui, document_controller):
        self.ui = ui
        self.document_controller = document_controller

        # list of export buttons (will be ordered in rows of 4 buttons)
        button_list = [
                "HAADF", "MAADF", "BF", "ABF",
                "LAADF", "SI-Survey", "SI-During", "SI-After",
                "SI-EELS", "EELS-sngl", "Ronchi"
                ]
        no_buttons_per_row = 4
        # initialise export dir field with empty string
        self.expdir_string = ""

        # function to construct the export directory string
        def get_export_dir_string():
            """ Reads the persistent date base directory from config file,
                and then
                constructs export directory path based on current year, date,
                microscopist, sampleID, sample description (i.e. sample_area).
                Returns the export directory path as string.
            """
            export_base_dir_with_year = get_export_base_dir_with_year(self.superstem_config_file)
            export_base_dir_with_year_path =  pathlib.Path(export_base_dir_with_year)
            date_string = datetime.datetime.now().strftime("%Y_%m_%d")
            #enforce empty string if field has no entry
            microscopist = str(self.__api.library.get_library_value("stem.session.microscopist")).upper() or ""
            sample = str(self.__api.library.get_library_value("stem.session.sample")) or ""
            sample_area =  str(self.__api.library.get_library_value("stem.session.sample_area")) or ""
            session_string = "_".join([ microscopist, sample, sample_area ])
            # pathlib "/" method to ;contruct export dir path:
            expdir_path = export_base_dir_with_year_path.joinpath(
                    date_string + "_" + session_string)
            logging.info("Exporting to: %s",expdir_path)
            return str(expdir_path)

        def write_persistent_vars(self):
            """ Writes export base directory path, export directory path and
                chosen export format to config files (superstem and Nion persistent data).
            """
            #current_superstem_settings = get_superstem_settings(self.superstem_config_file)
            #we haven't changed superstem_settings, no need to write them to file
            #write_superstem_config_file(self.superstem_config_file, current_superstem_settings)
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_directory', self.expdir_string)
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_filter', 'DigitalMicrograph Files files (*.dm3 *.dm4)')

        # === create main column widget
        column = ui.create_column_widget()
        column._widget.set_property("stylesheet", "background-color: #FFFFEC")

        # == create initialise new library button row
        new_library_button_row = ui.create_row_widget()
        new_library_button_row.add_spacing(3)
        new_library_label = ui.create_label_widget(_("Library:"))
        self.new_library_button = ui.create_push_button_widget(_("Initialise New Library"))
        self.new_library_button._widget.set_property("width", 150)
        new_library_button_row.add(new_library_label)
        new_library_button_row.add(self.new_library_button)
        new_library_button_row.add_spacing(2)
        def new_library_button_clicked():
            self.show_library_dialog("New Library", True, True)

        self.new_library_button.on_clicked = new_library_button_clicked


        # == create update export dir button row widget
        update_expdir_row = ui.create_row_widget()
        update_expdir_row.add_spacing(3)
        update_expdir_row_label = ui.create_label_widget("Export to DM:")
        self.update_expdir_button = ui.create_push_button_widget(_("Set Export Folder"))
        self.update_expdir_button._widget.set_property("width", 150)
        update_expdir_row.add(update_expdir_row_label)
        update_expdir_row.add_stretch()
        update_expdir_row.add(self.update_expdir_button)
        update_expdir_row.add_spacing(2)
        #update_expdir_row.add_stretch()

        def update_expdir_button_clicked():
            """ Writes updated export directory string from session meta data
                to persistent data and ensures export as DM file.
                Gets fired when expdir_button is clicked.
            """
            expdir_string = get_export_dir_string()
            self.expdir_field_edit.text = expdir_string
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_directory', expdir_string)
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_filter', 'DigitalMicrograph Files files (*.dm3 *.dm4)')

        self.update_expdir_button.on_clicked = update_expdir_button_clicked

        # == create editable export dir field row widget
        expdir_row = ui.create_row_widget()
        expdir_row.add_spacing(3)
        self.expdir_field_edit = ui.create_line_edit_widget("i")
        self.expdir_field_edit._widget.set_property("stylesheet", "background-color: white")
        self.expdir_field_edit._widget.set_property("width", 320)
        #doesn't work: self.expdir_field_edit.text = "<export dir set from session metadata>"

        def handle_expdir_field_changed(text):
            """ Handles manual edits to the expdir
                and writes any manual changes to persistent nion and superstem config
            """
            self.expdir_string = text
            write_persistent_vars(self)
            logging.info("Exporting to: %s", self.expdir_string)
            self.expdir_field_edit.request_refocus()  # not sure what this does

        self.expdir_field_edit.on_editing_finished = handle_expdir_field_changed
        self.expdir_field_edit.text = self.expdir_string
        expdir_row.add(self.expdir_field_edit)
        expdir_row.add_spacing(2)
        expdir_row.add_stretch()

        # == create quickexport label row widget
        quickexport_row = ui.create_row_widget()
        quickexport_row.add_spacing(3)
        self.quickexport_text =  ui.create_label_widget(_("Quick DM Export:"))
        self.quickexport_text._widget.set_property("width", 320)
        quickexport_row.add(self.quickexport_text)
        quickexport_row.add_spacing(2)
        
         # == create label row widget
        label_row = ui.create_row_widget()
        label_row.add_spacing(3)
        # define labels
        # properties parameters are not accepted here !?:
        self.label_no = ui.create_label_widget(_("No"))
        self.label_sub = ui.create_label_widget(_("Sub"))
        self.label_fov = ui.create_label_widget(_("FOV"))
        self.label_descr = ui.create_label_widget(_("Description"))
        self.label_no._widget.set_property("width", 40)
        self.label_sub._widget.set_property("width", 40)
        self.label_fov._widget.set_property("width", 40)
        label_row.add(self.label_no)
        label_row.add_spacing(1)
        label_row.add(self.label_sub)
        label_row.add_spacing(1)
        label_row.add(self.label_fov)
        label_row.add_spacing(1)
        label_row.add(self.label_descr)
        label_row.add_spacing(2)

        # == create editable fields row widget
        fields_row = ui.create_row_widget()
        fields_row.add_spacing(3)
        # define editable fields for field row
        self.fields_no_edit = ui.create_line_edit_widget()
        self.fields_sub_edit = ui.create_line_edit_widget()
        self.fields_fov_edit = ui.create_line_edit_widget()
        self.fields_descr_edit = ui.create_line_edit_widget()
        self.fields_no_edit._widget.set_property("stylesheet", "background-color: white")
        self.fields_sub_edit._widget.set_property("stylesheet", "background-color: white")
        self.fields_fov_edit._widget.set_property("stylesheet", "background-color: white")
        self.fields_descr_edit._widget.set_property("stylesheet", "background-color: white")
        self.fields_no_edit._widget.set_property("width", 40)
        self.fields_sub_edit._widget.set_property("width", 40)
        self.fields_fov_edit._widget.set_property("width", 40)

        def handle_no_changed(text):
            """ calls the update button state function for each export button
                and passes the current text in the No field
            """
            for button in self.button_widgets_list:
                self.update_button_state(button, no=text)
            # fields_nr_sub.request_refocus()

        def handle_sub_changed(text):
            for button in self.button_widgets_list:
                self.update_button_state(button, sub=text)
            # fields_fov_edit.request_refocus()

        def handle_fov_changed(text):
            for button in self.button_widgets_list:
                self.update_button_state(button, fov=text)
            # fields_descr_edit.request_refocus()

        def handle_descr_changed(text):
            for button in self.button_widgets_list:
                self.update_button_state(button, descr=text)
            # fields_descr_edit.request_refocus()

        # what happens when editing in field is done (= mouse click s.w. else)
        self.fields_no_edit.on_editing_finished = handle_no_changed
        self.fields_sub_edit.on_editing_finished = handle_sub_changed
        self.fields_fov_edit.on_editing_finished = handle_fov_changed
        self.fields_descr_edit.on_editing_finished = handle_descr_changed
        # add each field to fields row widget
        fields_row.add(self.fields_no_edit)
        fields_row.add_spacing(1)
        fields_row.add(self.fields_sub_edit)
        fields_row.add_spacing(1)
        fields_row.add(self.fields_fov_edit)
        fields_row.add_spacing(1)
        fields_row.add(self.fields_descr_edit)
        fields_row.add_spacing(2)
        #fields_row.add_stretch()

        # == create export button rows (contained in a column widget)
        self.button_column = ui.create_column_widget()
        # add button rows with 4 buttons each, taking buttons from button_list
        # line_no counts up to how many rows are required
        for line_no in range(divide_round_up(len(button_list), no_buttons_per_row)):
            button_row = self.create_button_line(line_no, button_list,
                                                 no_buttons_per_row)
            self.button_column.add(button_row)

        # == add the row widgets to the column widget
        column.add_spacing(8)
        column.add(new_library_button_row)
        column.add_spacing(5)
        column.add(update_expdir_row)
        column.add_spacing(3)
        column.add(expdir_row)
        column.add_spacing(8)
        column.add(quickexport_row)
        column.add_spacing(3)
        column.add(label_row)
        column.add(fields_row)
        column.add_spacing(3)
        column.add(self.button_column)
        column.add_spacing(5)
        column.add_stretch()

        # default state of export buttons:
        for button in self.button_widgets_list:
            # button._widget.enabled = False
            self.update_button_state(button)

        return column

    def update_button_state(self, button, **kwargs):
        """ This gets called for each editable field. It updates the relevant
            status boolean based on text in the field, and then the overall
            status boolean. Then enables/disables export button widget
            depending on the overall status boolean.
            -----------
            Parameters: button = the current export button widget
                        kwargs = the name and text value of the editable field
        """
        # update current status of each editable field
        if 'no' in kwargs and kwargs['no'] != "":
            self.have_no = True
        elif 'no' in kwargs and kwargs['no'] == "":
            self.have_no = False
        if 'sub' in kwargs and kwargs['sub'] != "":
            self.have_sub = True
        elif 'sub' in kwargs and kwargs['sub'] == "":
            self.have_sub = False
        if 'fov' in kwargs and kwargs['fov'] != "":
            self.have_fov = True
        elif 'fov' in kwargs and kwargs['fov'] == "":
            self.have_fov = False
        if 'descr' in kwargs and kwargs['descr'] != "":
            self.have_descr = True
        elif 'descr' in kwargs and kwargs['descr'] == "":
            self.have_descr = False

        # only if related status booleans of required fields
        # (No, FOV and Description) are all True can we set all good to go
        if self.have_no and self.have_fov and self.have_descr:
            self.all_good = True
        else:
            self.all_good = False

        def update():
            """ enables/disables button widget
            """
            if self.all_good:
                button._widget.enabled = True
            else:
                button._widget.enabled = False

        self.__api.queue_task(update)



    def create_button_line(self, index, button_list, no_buttons_per_row):
        """ Creates a row of up to 4 buttons inside a column.
            -----------
            Parameters: index = current line_no of export button rows
                        button_list = list of strings with button names
        """
        # === create main column in which the rows goes
        column = self.ui.create_column_widget()
        row = self.ui.create_row_widget()
        row.add_spacing(3)
        def export_button_clicked(button_list_index):
            """ Renames selected DISPLAY item and saves as DM to the selected
                export directory.
                Note, all export buttons are disabled until all required fields
                (No, FOV, descripton) are filled in.
                -----------
                Parameters: button_list_index = selected export button string
            """

            writer = ImportExportManager.ImportExportManager().get_writer_by_id(self.io_handler_id)
            prefix = get_prefix_string(self.fields_no_edit.text)
            postfix = get_postfix_string(self.fields_sub_edit.text,
                                         self.fields_fov_edit.text,
                                         self.fields_descr_edit.text)
            item = self.__api.application.document_controllers[0]._document_controller.selected_display_item
            item.title = (prefix + str(button_list[button_list_index])
                          + postfix)
            # get latest export directory from persistent config
            directory_string = self.__api.application.document_controllers[0]._document_controller.ui.get_persistent_string('export_directory')
            logging.info("Exporting to %s ", directory_string)
            filename = "{0}.{1}".format(item.title, writer.extensions[0])
            export_path = pathlib.Path(directory_string).joinpath(filename)

            if not pathlib.Path.is_dir(export_path.parent):
                export_path.parent.mkdir(parents=True)  # mkdir -p
            else:
                logging.info("- Export Directory already exists")

            if not pathlib.Path.is_file(export_path):
                ImportExportManager.ImportExportManager().write_display_item_with_writer(writer, item, export_path)
                logging.info("- %s", export_path.name)
            else:
                # launch popup dialog if filename already exists
                logging.info("- Could not export - file exists")
                self.show_warning_dialog("Could not export - file exists", True, False)

        # == make specific export buttons
        # don't know how many buttons there are, so it's possible to have
        # not enough to fill a row of 4
        try:
            self.button1 = self.ui.create_push_button_widget(_(str(button_list[no_buttons_per_row*index])))
            row.add(self.button1)
            row.add_spacing(1)
            self.button_widgets_list.append(self.button1)
            self.button1.on_clicked = functools.partial(export_button_clicked, (no_buttons_per_row*index))
        except IndexError:
            # logging.info("export_button_clicked: IndexError at Button1, row %s", index)
            pass
        try:
            self.button2 = self.ui.create_push_button_widget(_(str(button_list[(no_buttons_per_row*index)+1])))
            row.add(self.button2)
            row.add_spacing(1)
            self.button_widgets_list.append(self.button2)
            self.button2.on_clicked = functools.partial(export_button_clicked, (no_buttons_per_row*index)+1)
        except IndexError:
            # logging.info("export_button_clicked: IndexError at  Button2, row %s", index)
            pass
        try:
            self.button3 = self.ui.create_push_button_widget(_(str(button_list[(no_buttons_per_row*index)+2])))
            row.add(self.button3)
            row.add_spacing(1)
            self.button_widgets_list.append(self.button3)
            self.button3.on_clicked = functools.partial(export_button_clicked, (no_buttons_per_row*index)+2)
        except IndexError:
            # logging.info("export_button_clicked: IndexError at Button3, row %s", index)
            pass
        try:
            self.button4 = self.ui.create_push_button_widget(_(str(button_list[(no_buttons_per_row*index)+3])))
            row.add(self.button4)
            row.add_spacing(2)
            self.button_widgets_list.append(self.button4)
            self.button4.on_clicked = functools.partial(export_button_clicked, (no_buttons_per_row*index)+3)
        except IndexError:
            # logging.info("export_button_clicked: IndexError at Button4, row %s ", index)
            pass
        #row.add_stretch()

        column.add(row)
        column.add_spacing(0)

        return column


class PanelSuperSTEMExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.examples.quickdmexport_panel"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__panel_ref = api.create_panel(PanelSuperSTEMDelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__panel_ref.close()
        self.__panel_ref = None
