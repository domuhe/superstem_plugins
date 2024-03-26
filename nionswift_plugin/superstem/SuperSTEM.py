# standard libraries
import gettext
import logging
import datetime
import os
import pathlib
import functools
import typing
import json
import subprocess

# local libraries
from nion.ui import Dialog, UserInterface
from nion.swift.model import ImportExportManager
from nion.swift.model import Cache
from nion.swift.model import Profile
from nion.swift import DocumentController



_ = gettext.gettext


# global flag to indicate whether "Set Export Folder" has been run at least once
flag_set_exp_dir = 0

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
                    #logging.info("- SuperSTEM settings are %s", superstem_settings)
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

def get_default_project(superstem_config_file):
    """
    Reads default project from superstem config file.
    If there is no entry it writes warning to console.
    Swift works without it, only the "Finish & Load Default Proj" button will not work correctly.
    """
    default_project = get_superstem_settings(superstem_config_file).get('default_project')
    if default_project is None:
        logging.info("YOU NEED TO SET A DEFAULT PROJECT IN SUPERSTEM CUSTON JSON FILE!")
    return str(default_project)

def get_compress_program(superstem_config_file):
    compress_program = get_superstem_settings(superstem_config_file).get('compress_program')
    return str(compress_program)
    
def get_hashes_program(superstem_config_file):
    hashes_program = get_superstem_settings(superstem_config_file).get('hashes_program')
    return str(hashes_program)

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
         
logging.info("Loaded SuperSTEM Panel")

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
    
    20240312; DMH:
        This version of the plugin creates new feature of "compress last project". At the end of a session one clicks
        on "Finish and Load Default Project". Afterwards one clicks on "Compress last project" and the plugin
        runs compress.bat to create compressed archive of raw nionswift library in New_Data, then tests the archive and then
        runs hashesNew.bat to calculate hashes and filesizes for all files in New_Data and werites them to a hashes file
        in New_Data, ready to be uploaded to cask via GoodSync.
        .
        This now requires a modified switch_project_reference function in Application.py in the main Nion code.
        This provides a hook to update sstem_last_project_dir and sstem_current_project_dir persistent variables
        in nionswift_appdata.json whenever a project is loaded or created.
        We use three new variables in superstem_customisation.json: default_project, compress_program, hashes_program
    20230321; DMH:
        Re-enabling top dir for Nion Swift library and nsproj pairs.
        Adding "S" to sample no in Initialise New Library automatically.
    20230307; DMH:
        Added a field and toggle button with which to change the DM version of the
        output data files. Default is DM3.
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
        self.__loaddefproj_dialog_open = False

        # initial edit status of editable rename fields
        self.have_no = False
        self.have_sub = False
        self.have_fov = False
        self.have_descr = False
        self.exp_all_good = False
        #logging.info("expallgood %s", self.exp_all_good)
        # keep track of export buttons here
        self.button_widgets_list = []
        # get current year
        self.year = datetime.datetime.now().year
        # dmver toggle button
        self.quickexport_dmver_toggle_button_state="3"
        
        # we only export to DM
        self.io_handler_id = "dm-io-handler"

        # SuperSTEM config file
        self.superstem_config_file = api.application.configuration_location / pathlib.Path("superstem_customisation.json")
 
        

#####
    def show_loaddefproj_dialog(self, title_string, have_ok=True, have_cancel=True):

        api = self.api
        myapi = self.__api
        superstem_config_file = self.superstem_config_file
        #proref = myapi.application._application.profile.get_project_reference(profile.last_project_reference)
        #proref = myapi.application.__application.profile()
        #proref = myapi.application.__application.project_refence.title
        #logging.info("shloadefproj project reference: %s", proref)
        #myapi.application._application. show_open_project_dialog()
        # this puts function in the scope of the class LibraryDialog;  - not necessary
        #get_data_base_dir_with_year_fn = get_data_base_dir_with_year(superstem_config_file)
      

        class LoadDefProjDialog(Dialog.ActionDialog):
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

                defproj_name = get_default_project(superstem_config_file)

                # ==== main column widget ====
                column = self.ui.create_column_widget()           

                # === Ok Cancel row  ===
                ok_cancel_row = self.ui.create_row_widget()
                #ok_cancel_row.add_spacing(1)    

                def on_cancel_clicked():
                    if self.on_reject:
                        self.on_reject()
                    # Return 'True' to tell Swift to close the Dialog
                    return True

                if include_cancel:
                    self.add_button('Cancel', on_cancel_clicked)
                    #ok_cancel_row.add_stretch()
                    
                def handle_loaddefproj():
                    #logging.info("handle_loaddefproj was called")
                    if defproj_name != "":
                        # to ensure the application does not close upon closing the last window, force it
                        # to stay open while the window is closed and another reopened.
                        with myapi.application._application.prevent_close():

                            if os.path.exists(defproj_name):
                                logging.info("defproj_name: %s", defproj_name)
                                # set the current project dir as last project dir in preparation of loading the default project
                                last_project_dir = myapi.application.document_controllers[0]._document_controller.ui.get_persistent_string('sstem_current_project_dir')
                                # and write to  presistent config:
                                #myapi.application.document_controllers[0]._document_controller.ui.set_persistent_string('sstem_last_project_dir', last_project_dir)
                                #logging.info("last_project_dir %s", last_project_dir)
                                # get project_reference for default project
                                #myapi.application._application.create_project_reference(pathlib.Path(defproj_name))
                                project_reference =  myapi.application._application.profile.open_project(pathlib.Path((defproj_name)))
                                #logging.info("project_reference in loaddefpro: %s %s", project_reference, project_reference.title)
                                #  close and load def project
                                myapi.application._application.switch_project_reference(project_reference)
                                    
                                return True
                            return False

                    else:
                         logging.info("----missing defproj_name !!!")         

                if include_ok:
                    # clicking on this button loads default project
                    # logging.info("clicked on LoadDefProj button")
                    self.add_button(_("Close Project and Load Default Project"), handle_loaddefproj)                    


                # ==== Adding rows to main column ====
                column.add(ok_cancel_row)
                #column.add_stretch()

                self.content.add(column)

            def about_to_close(self, geometry: str, state: str) -> None:
                """
                Required to properly close the Dialog.
                """
                if self.on_reject:
                    self.on_reject()
                super().about_to_close(geometry, state)

        # We track open dialogs to ensure that only one dialog can be open at a time
        if not self.__loaddefproj_dialog_open:
            self.__loaddefproj_dialog_open = True
            dc = self.__api.application.document_controllers[0]._document_controller
            # This function will inform the main panel that the dialog has been closed, so that it will allow
            # opening a new one
            def report_dialog_closed():
                self.__loaddefproj_dialog_open = False
            # We pass in `report_dialog_closed` so that it gets called when the dialog is closed.
            # If you want to invoke different actions when the user clicks 'OK' and 'Canclel', you can of course pass
            # in two different functions for `on_accept` and `on_reject`.
            LoadDefProjDialog(dc.ui, on_accept=report_dialog_closed, on_reject=report_dialog_closed).show()
            
#####


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
                #logging.info("allgood %s", self.all_good)


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
                    [_("Sample"), _("Sample Number <nnnn>"), "sample"],
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
                        "S" + field_line_edit_widget_map["sample"].text,
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
                             # if site field is using superstem setting sile we need to update global
                             # global session metadata with empty stringnew value
                             session_metadata_key = "stem.session." + str(field_id)
                             api.library.set_library_value(session_metadata_key, line_edit_widget.text)
                    elif field_id == "instrument":
                        line_edit_widget.text = myapi.library.get_library_value("stem.session.instrument")
                        if line_edit_widget.text ==  "":
                             line_edit_widget.text = get_superstem_settings(superstem_config_file).get('superstem_instrument')
                             # if site field is using superstem setting sile we need to update global
                             # global session metadata with empty stringnew value
                             session_metadata_key = "stem.session." + str(field_id)
                             api.library.set_library_value(session_metadata_key, line_edit_widget.text)
                    # ensure that Session panel Task field is cleared when widget is called 
                    # by updating global session metadata with empty string
                    session_metadata_key = "stem.session." + str("task")
                    api.library.set_library_value(session_metadata_key, "")
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
                            # we want a top directory for each new library and nsproj pair:
                            workspace_dir = os.path.join(self.data_base_dir_with_year, library_name_field.text + "_Raw")
                            
                            # no top directory, library and nsproj files all in a flat directory:
                            # workspace_dir = self.data_base_dir_with_year
                            Cache.db_make_directory_if_needed(workspace_dir)
                            # Nionswift no longer uses *.nslib -> *.nsproj, disable this:
                            #path = os.path.join(workspace_dir, "Nion Swift Workspace.nslib")
                            #if not os.path.exists(path):
                            #    with open(path, "w") as fp:
                            #        json.dump({}, fp)
                            #if os.path.exists(path):
                            
                            # create project file if workspace_dir exists
                            if os.path.exists(workspace_dir):
                                myapi.application._application.create_project_reference(pathlib.Path(workspace_dir), library_name_field.text)
                                last_workspace_dir = myapi.application.document_controllers[0]._document_controller.ui.get_persistent_string('current_workspace_directory')
                                myapi.application.document_controllers[0]._document_controller.ui.set_persistent_string('current_workspace_directory', workspace_dir)
                                myapi.application.document_controllers[0]._document_controller.ui.set_persistent_string('last_workspace_directory', last_workspace_dir)
                                
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
                    # clicking on this button loads new library
                    self.add_button(_("Create New Library and Session"), handle_new)


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
        self.quickexport_dmver_toggle_button_state = "3"

    def create_panel_widget(self, ui, document_controller):
        self.ui = ui
        self.document_controller = document_controller

        # list of export buttons (will be ordered in rows of 4 buttons)
        button_list = [
                "HAADF", "MAADF", "BF", "ABF",
                "LAADF", "SI-Survey", "SI-HAADF", "SI-After",
                "SI-EELS", "EELS-single", "EELS-multi","Ronchi"
                ]
        no_buttons_per_row = 4
        # initialise export dir field with empty string
        self.expdir_string = ""
        self.lastdir_string = ""

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
            sample = "S" + str(self.__api.library.get_library_value("stem.session.sample")) or ""
            sample_area =  str(self.__api.library.get_library_value("stem.session.sample_area")) or ""
            task =  str(self.__api.library.get_library_value("stem.session.task")) or ""
            # have decided not to include task=project number in folder name
            #if task != "":
            #    prefix_task = "p" + task
            #    session_string = "_".join([ microscopist, sample, sample_area, prefix_task ])
            #else:
            session_string = "_".join([ microscopist, sample, sample_area ])
            ## pathlib "/" method to ;contruct export dir path:
    
            expdir_path = export_base_dir_with_year_path.joinpath(
                    date_string + "_" + session_string)
            logging.info("- Exporting to: %s",expdir_path)
            return str(expdir_path)

        def write_persistent_export_vars(self):
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
        self.new_library_button._widget.set_property("width", 200)
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
        self.update_expdir_button = ui.create_push_button_widget(_("Set Export Folder From Session Data"))
        self.update_expdir_button._widget.set_property("width", 200)
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
            global flag_set_exp_dir
            expdir_string = get_export_dir_string()
            if expdir_string != "":
                # logging.info("flag is %s", flag_set_exp_dir)
                flag_set_exp_dir = 1
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
            write_persistent_export_vars(self)
            logging.info("- Now exporting to: %s", self.expdir_string)
            self.expdir_field_edit.request_refocus()  # not sure what this does


        self.expdir_field_edit.on_editing_finished = handle_expdir_field_changed
        self.expdir_field_edit.text = self.expdir_string
        expdir_row.add(self.expdir_field_edit)
        expdir_row.add_spacing(2)
        expdir_row.add_stretch()

        # == create quickexport label row widget
        quickexport_row = ui.create_row_widget()
        quickexport_row.add_spacing(2)
        self.quickexport_text =  ui.create_label_widget(_("Quick DM Export: <sup> (\"Sub\" optional)</sup>"))
        self.quickexport_text._widget.set_property("width", 220)
        quickexport_dmversion_label = ui.create_label_widget(_("DM Version:"))
        self.quickexport_dmver_edit = ui.create_line_edit_widget()
        self.quickexport_dmver_edit._widget.placeholder_text = self.quickexport_dmver_toggle_button_state
        self.quickexport_dmver_edit._widget.set_property("stylesheet", "background-color: white")
        self.quickexport_dmver_edit._widget.set_property("width", 20)
        self.quickexport_dmver_toggle_button = ui.create_push_button_widget(_("⟲"))
        self.quickexport_dmver_toggle_button._widget.set_property("width", 25)
        
        quickexport_row.add(self.quickexport_text)
        quickexport_row.add(quickexport_dmversion_label)
        quickexport_row.add(self.quickexport_dmver_edit)
        quickexport_row.add(self.quickexport_dmver_toggle_button)
        quickexport_row.add_spacing(0)
        
        def handle_dmver_changed(text):
            """ This is actually not needed to assign the supplied text in the field
                to self.quickexport_dmver_edit.text.
                We just use it to feed back the chosen DM version to the user
                Note: one can either change DM version manually with the field
                      or using the toggle button quickexport_dmver_toggle_button
                If typing other than 3 or 4 we default back to 3
            """
            dmversion=text
            if dmversion != "3" and dmversion != "4":
                print(f'- Incorrect DM version, reverting back to version 3!')
                self.quickexport_dmver_edit.text = "3"
                dmversion = "3"
            print(f'- DM version {dmversion}')

        self.quickexport_dmver_edit.on_editing_finished = handle_dmver_changed
        
        def quickexport_dmver_toggle_button_clicked():
            """ on clicking the dmver_toggle_button we change the toggle_button_state to the other
                DM version and assign the value of toggle_button_state to the quickexport_dmver_edit field.
                You can still manually type the version in the dmver_edit field and override this. 
                With the next click on the dmver_toggle_button we default back to DM version 3.
            """
            if  self.quickexport_dmver_toggle_button_state == "3":
                self.quickexport_dmver_toggle_button_state = "4"
            elif self.quickexport_dmver_toggle_button_state == "4":
                self.quickexport_dmver_toggle_button_state = "3"
            else:
                self.quickexport_dmver_toggle_button_state = "3"

            self.quickexport_dmver_edit._widget.placeholder_text = self.quickexport_dmver_toggle_button_state        
            self.quickexport_dmver_edit.text = self.quickexport_dmver_toggle_button_state
            print(f'- DM version {self.quickexport_dmver_toggle_button_state}')
            #logging.info("quickexport clicked")
                
        self.quickexport_dmver_toggle_button.on_clicked = quickexport_dmver_toggle_button_clicked
        
        # # == create label row widget
        # label_row = ui.create_row_widget()
        # label_row.add_spacing(3)
        # # define labels
        # # properties parameters are not accepted here !?:
        # self.label_no = ui.create_label_widget(_("No"))
        # self.label_sub = ui.create_label_widget(_("Sub"))
        # self.label_fov = ui.create_label_widget(_("FOV"))
        # self.label_descr = ui.create_label_widget(_("Description"))
        # self.label_no._widget.set_property("width", 40)
        # self.label_sub._widget.set_property("width", 40)
        # self.label_fov._widget.set_property("width", 40)
        # label_row.add(self.label_no)
        # label_row.add_spacing(1)
        # label_row.add(self.label_sub)
        # label_row.add_spacing(1)
        # label_row.add(self.label_fov)
        # label_row.add_spacing(1)
        # label_row.add(self.label_descr)
        # label_row.add_spacing(2)

        # == create editable fields row widget
        fields_row = ui.create_row_widget()
        fields_row.add_spacing(3)
        # define editable fields for field row
        self.fields_no_edit = ui.create_line_edit_widget()
        self.fields_no_edit._widget.placeholder_text = "No"
        self.fields_sub_edit = ui.create_line_edit_widget()
        self.fields_sub_edit._widget.placeholder_text = "Sub"
        self.fields_fov_edit = ui.create_line_edit_widget()
        self.fields_fov_edit._widget.placeholder_text = "FOV"
        self.fields_descr_edit = ui.create_line_edit_widget()
        self.fields_descr_edit._widget.placeholder_text = "Description  (hit RET when finished)"
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

        # == create finish and reload button row widget
        finish_reload_row = ui.create_row_widget()
        finish_reload_row.add_spacing(3)
        self.finish_reload_button = ui.create_push_button_widget(_("Finish && Load Default Proj"))
        self.finish_reload_button._widget.set_property("width", 180)
        self.finish_reload_compress_button = ui.create_push_button_widget(_("Compress Last Proj"))
        self.finish_reload_compress_button._widget.set_property("width", 150)
        finish_reload_row.add_stretch()
        finish_reload_row.add(self.finish_reload_button)
        finish_reload_row.add_spacing(2)
        finish_reload_row.add(self.finish_reload_compress_button)
        
        def finish_reload_button_clicked():
            #logging.info("have clicked on main load def proj button")
            self.show_loaddefproj_dialog("Finish && Load Default Project", True, True)         

        self.finish_reload_button.on_clicked = finish_reload_button_clicked

        def finish_reload_compress_button_clicked():
            compress_program = get_compress_program(self.superstem_config_file)
            # compress_program = r"F:\StaffData\dmuecke\Nionswift-Development\Saved_Data\compress.bat"
            hashes_program = get_hashes_program(self.superstem_config_file)
            #hashes_program = r"F:\StaffData\dmuecke\Nionswift-Development\Saved_Data\hashesNew.bat"
            logging.info("hp %s", hashes_program)
            last_proj_dir_string = self.__api.application.document_controllers[0]._document_controller.ui.get_persistent_string('sstem_last_project_dir')
            last_proj_dir_path, last_proj_name = last_proj_dir_string.rsplit("\\",1)
            # project name without ".nsproj":
            last_proj_dir_name = last_proj_name.rsplit(".nsproj",1)[0]

            #logging.info("lpds, lpn %s %s", last_proj_dir_name, last_proj_name)
            export_base_directory = get_export_base_dir(self.superstem_config_file)
            output_dir = export_base_directory + "\\" + last_proj_dir_name
            output_archive_file = output_dir + "\\" + last_proj_dir_name + "_Raw.zip"
            # MAKE OUTPUT DIR IF NOT EXISTS
            os.makedirs(output_dir, exist_ok=True)
  

            #logging.info("of %s", output_file)
            # enclosing command line parameters with quotes
            # compress bat file, compressed archive name, last project, hashes bat file, export base dir
            compress_command = " \"" + compress_program + "\" \"" + output_archive_file  + "\"  \"" + last_proj_dir_path + "\"  \"" + hashes_program + "\" \"" + export_base_directory + "\" && echo DONE || echo ERROR Something is wrong"

            logging.info("- Running now: %s", compress_program)
            p = subprocess.Popen(compress_command,shell=True)
            # ... do other stuff while subprocess is running
            #p.terminate()
            
        self.finish_reload_compress_button.on_clicked = finish_reload_compress_button_clicked
        
        # == create last project row widget
        lastproj_row = ui.create_row_widget()
        lastproj_row.add_spacing(3)
        lastproj_row_label = ui.create_label_widget("Last Proj:")
        lastproj_row.add(lastproj_row_label)
        lastproj_row.add_stretch()
                
        lastproj_dir_string = self.__api.application.document_controllers[0]._document_controller.ui.get_persistent_string('sstem_last_project_dir')
        logging.info("- Last Project: %s", lastproj_dir_string)
        currentproj_dir_string = self.__api.application.document_controllers[0]._document_controller.ui.get_persistent_string('sstem_current_project_dir')
        logging.info("- Current Project: %s", currentproj_dir_string)

        self.lastproj_field_edit = ui.create_line_edit_widget("h")
        self.lastproj_field_edit._widget.set_property("stylesheet", "background-color: white")
        self.lastproj_field_edit._widget.set_property("width", 270)

        def write_persistent_lastproj_vars(self):
            """ Writes export base directory path, export directory path and
                chosen export format to config files (superstem and Nion persistent data).
            """
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('sstem_last_project_dir', self.lastproj_string)
            
        def handle_lastproj_field_changed(text):
            """ Handles manual edits to the lastproj field
                and writes any manual changes to persistent nion and superstem config
            """
            self.lastproj_string = text
            write_persistent_lastproj_vars(self)
            logging.info("- Last Project is now : %s", self.lastproj_string)
            self.exp_all_good = False
            flag_set_exp_dir = 0
            self.lastproj_field_edit.request_refocus()  # not sure what this does

        self.lastproj_field_edit.on_editing_finished = handle_lastproj_field_changed
        self.lastproj_field_edit.text = lastproj_dir_string
        lastproj_row.add(self.lastproj_field_edit)
        lastproj_row.add_spacing(2)
        lastproj_row.add_stretch()
            
        # == add the row widgets to the column widget
        column.add_spacing(8)
        column.add(new_library_button_row)
        column.add_spacing(5)
        column.add(update_expdir_row)
        column.add_spacing(3)
        column.add(expdir_row)
        column.add_spacing(9)
        column.add(quickexport_row)
        column.add_spacing(3)
        #column.add(label_row)
        column.add(fields_row)
        column.add_spacing(3)
        column.add(self.button_column)
        column.add_spacing(5)
        column.add(lastproj_row)
        column.add_spacing(3)
        column.add(finish_reload_row)
        
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

        # only if related status booleans of required fields (No, FOV and Description)
        # are all True and exp_dir_path is defined (i.e. SetExport Folder has run at
        # least once) can we set all good to go
        #logging.info("flag_set_exp_dir %s", str(flag_set_exp_dir))
        if self.have_no and self.have_fov and self.have_descr and flag_set_exp_dir == 1:
            self.exp_all_good = True
        else:
            self.exp_all_good = False

 
        def update():
            """ enables/disables button widget
            """
            if self.exp_all_good:
                button._widget.enabled = True
            else:
                button._widget.enabled = False
            #logging.info("update button status %s %s", self.exp_all_good, button._widget.enabled)

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
            if len(directory_string) == 0:
                logging.info("- Error!  Export directory variable empty!")
            else:
                logging.info("- Exporting to %s ", directory_string)

            ## filename is quick export concatenation plus dm3 or dm4 extension            
            #filename = "{0}.{1}".format(item.title, writer.extensions[0])
            # we default to writing dm4 files:
            #filename = "{0}.{1}".format(item.title, "dm4")
            # we take supplied dmversion by quickexport_dmver_edit field
            # (or, via dmver_toggle_button)
            # if = "4", set to 4, else default to "dm3"
            if str(self.quickexport_dmver_edit.text) == "4":
                dmextension="dm" + str(self.quickexport_dmver_edit.text)
            elif str(self.quickexport_dmver_edit.text) == "3":
                dmextension="dm" + str(self.quickexport_dmver_edit.text)
            else:
                dmextension="dm3"
                self.quickexport_dmver_edit.text = "3"
                
            print(f'- dmextension {dmextension}')
            filename = "{0}.{1}".format(item.title, dmextension)
            export_path = pathlib.Path(directory_string).joinpath(filename)

            if not pathlib.Path.is_dir(export_path.parent):
                logging.info("- Creating Export Dir")
                export_path.parent.mkdir(parents=True)  # mkdir -p
            else:
                logging.info("- Export Directory exists")
                pass

            if not pathlib.Path.is_file(export_path):
               ImportExportManager.ImportExportManager().write_display_item_with_writer(writer, item, export_path)
               logging.info("- %s", export_path.name)
            else:
                # launch popup dialog if filename already exists
                logging.info("----- COULD NOT EXPORT - FILE EXISTS !!! -----")
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

