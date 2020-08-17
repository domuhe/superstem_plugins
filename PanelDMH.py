# standard libraries
import gettext
import logging
import threading
import datetime
import os
import pathlib
import functools
import typing
import asyncio
import functools
import gettext
import pkgutil
import string
import sys

# local libraries
from nion.swift import Panel
from nion.swift.model import ApplicationData
from nion.swift.model import DataGroup
from nion.ui import Dialog, UserInterface
from nion.swift.model import DataGroup
from nion.swift.model import ImportExportManager

_ = gettext.gettext


# utility functions
def divide_round_up(x,n):
    """ returns integer division rounded up """
    return int((x + (n -1))/n)

# functions to handle prefix and postfix strings for renaming
def get_prefix_string(no_field_string):
    #pad No with leading zeros  
    prefix_string = str(no_field_string.zfill(3)) + "_"  
    return prefix_string
def get_postfix_string(sub_field_string,fov_field_string,descr_field_string):
    if str(sub_field_string) == "" :
        postfix_string = "_" + str(fov_field_string) + "nm_" + str(descr_field_string)
    else:
        postfix_string = "_" + str(sub_field_string) + "_" + str(fov_field_string) + "nm_" + str(descr_field_string)   
    return postfix_string


class PanelQuickDMExportDelegate:
    """
    This panel plugin allows to set the persistent export directory from the session metadata
    and then to rename and export as DM file a display item based on four editable fields
    -
    Note: If you keep the Nionswift Library open overnight and then export the files, 
    the default will be that the date of the export directory will not match the date of the Library.
    In this case one should manually change the date in the Export Dir field.
    ======================================================================================
    Revisions:
        
    20200811:
    DMH:  initial version
    """
    
    def __init__(self, api):
        self.__api = api
        self.panel_id = "quickdmexport-panel"
        self.panel_name = _("Quick DM Export")
        self.panel_positions = ["left", "right"]
        self.panel_position = "right"
        self.api = api
        
        # initial edit status of editable fields
        self.have_no = False
        self.have_sub = False
        self.have_fov = False
        self.have_descr = False
        # keep track of export buttons here
        self.button_widgets_list = []

        # get current datetime
        self.now = datetime.datetime.now()
        
        # we only export to DM 
        self.io_handler_id = "dm-io-handler"
        self.writer = ImportExportManager.ImportExportManager().get_writer_by_id(self.io_handler_id)
    
    def create_panel_widget(self, ui, document_controller):
        self.ui = ui
        self.document_controller = document_controller
        #initialise export dir field with empty string
        self.expdir_string = ""
        
        # function to cosntruct the export directory string
        def get_export_dir_string():            
            #site based base directory for exports
            expdir_base_string = self.__api.application.document_controllers[0]._document_controller.ui.get_persistent_string('export_base_directory')
            #fall back to /tmp/SSTEMData/<year> or C:/tmp/SSTEMData/<year>
            if expdir_base_string == None:
                expdir_base_path = pathlib.Path('/tmp/SSTEMData/')       
            else:
                expdir_base_path = pathlib.Path(expdir_base_string)
            expdir_date_string = "_".join([str(self.now.year), str(self.now.month), str(self.now.day)])
            expdir_session_string = "_".join([
                    str(self.__api.library.get_library_value("stem.session.microscopist")), 
                    str(self.__api.library.get_library_value("stem.session.sample")),
                    str(self.__api.library.get_library_value("stem.session.sample_area"))
            ])
            
            # pathlib "/" method to ;contruct export dir path:
            expdir_path = expdir_base_path / str(self.now.year) / "doro" /  "_".join([expdir_date_string, expdir_session_string])                        
            logging.info("expdir %s", expdir_path)
            return str(expdir_path)
        
        def write_persistent_vars(self):            
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_base_directory', expdir_base_string) 
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_directory', expdir_string)                                                
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_filter', 'DigitalMicrograph Files files (*.dm3 *.dm4)')
            logging.info("have set expdir")       

                                            
        #### create column widget
        column = ui.create_column_widget()


        ### update export dir button row
        update_expdir_row = ui.create_row_widget()
        ## create button
        self.update_expdir_button = ui.create_push_button_widget(_("Set Exp Dir from Session Metadata"))
        ## add button to row
        update_expdir_row.add(self.update_expdir_button)
        ## define on_clicked event/signal?     
        def update_expdir_button_clicked():
            # writes updated export directory string from session meta data to persistent data and ensures export as DM file
            expdir_string = get_export_dir_string()
            self.expdir_field_edit.text = expdir_string
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_directory', expdir_string)
            self.__api.application.document_controllers[0]._document_controller.ui.set_persistent_string('export_filter', 'DigitalMicrograph Files files (*.dm3 *.dm4)')
        ## define listening slot
        self.update_expdir_button.on_clicked = update_expdir_button_clicked
        update_expdir_row.add_spacing(5)              
        ## add label
        update_expdir_row.add(ui.create_label_widget(_("Export Dir:")))
        update_expdir_row.add_spacing(2)        
        update_expdir_row.add_stretch             


        ### editable export dir field row
        expdir_row = ui.create_row_widget()
        self.expdir_field_edit = ui.create_line_edit_widget()
        def handle_expdir_field_changed(text):
            # can overwrite export directory in persistent data with the modified text in the field
            self.expdir_string = text
            write_persistent_vars(self)
            self.expdir_field_edit.request_refocus()   #not sure what this does?
        self.expdir_field_edit.on_editing_finished = handle_expdir_field_changed
        self.expdir_field_edit.text = self.expdir_string 
        expdir_row.add(self.expdir_field_edit)
        expdir_row.add_spacing(2)
        update_expdir_row.add_stretch   

        ### create label row
        label_row = ui.create_row_widget()
        ## define labels
        # properties parameters are not accepted here? edit_row.add(ui.create_label_widget("dummy", properties={"width": 100}))
        label_row.add(ui.create_label_widget(_("No")))
        label_row.add_spacing(1)
        label_row.add(ui.create_label_widget(_(" Sub")))
        label_row.add_spacing(1)
        label_row.add(ui.create_label_widget(_(" FOV")))
        label_row.add_spacing(1)
        label_row.add(ui.create_label_widget(_(" Description")))    
        label_row.add_spacing(2)
        #label_row.add_stretch()  
        
        ### create editable fields row widget
        fields_row = ui.create_row_widget()
        ## define editable fields for field row
        self.fields_no_edit =  ui.create_line_edit_widget()
        self.fields_sub_edit = ui.create_line_edit_widget()
        self.fields_fov_edit = ui.create_line_edit_widget()
        self.fields_descr_edit = ui.create_line_edit_widget()
        ## define what happens when editable fields have changed                        
        def handle_no_changed(text):
            logging.info(text)
            self.update_button_state(self.haadf_button, no=True)
            for button in self.button_widgets_list:                
                self.update_button_state(button, no=True)
            #fields_nr_sub.request_refocus()            
        def handle_sub_changed(text):            
            logging.info(text)
            self.update_button_state(self.haadf_button, sub=True)
            for button in self.button_widgets_list:                
                self.update_button_state(button, sub=True)            
            #fields_fov_edit.request_refocus()                       
        def handle_fov_changed(text):
            logging.info(text)
            self.update_button_state(self.haadf_button, fov=True)
            for button in self.button_widgets_list:                
                self.update_button_state(button, fov=True)            
            #fields_descr_edit.request_refocus()
        def handle_descr_changed(text):
            logging.info(text)
            self.update_button_state(self.haadf_button, descr=True)
            for button in self.button_widgets_list:                
                self.update_button_state(button, descr=True)            
            #fields_descr_edit.request_refocus()        
        ## define editing_finished event
        #"calling" handle functions w/o () only passes the function object (it does not invoke the function)
        self.fields_no_edit.on_editing_finished = handle_no_changed
        self.fields_sub_edit.on_editing_finished = handle_sub_changed
        self.fields_fov_edit.on_editing_finished = handle_fov_changed
        self.fields_descr_edit.on_editing_finished = handle_descr_changed        
        ## add each field to fields row widget
        fields_row.add(self.fields_no_edit)
        fields_row.add_spacing(1)
        fields_row.add(self.fields_sub_edit)
        fields_row.add_spacing(1)
        fields_row.add(self.fields_fov_edit)
        fields_row.add_spacing(1)
        fields_row.add(self.fields_descr_edit)
        fields_row.add_spacing(2)
        fields_row.add_stretch()       
       

        ### create export button rows (contained in a column widget)
        #!!! this could be read from persistent data to allow user to configure buttons via config file        
        button_list = [
                "HAADF", "MAADF", "BF", "ABF", 
                "LAADF", "SI-Survey", "SI-During", "SI-After",
                "SI-EELS", "EELS-sngl", "Ronchi"
                ]
        self.button_column = ui.create_column_widget()
        # add button rows with 4 buttons from button_list each
        for index in range(divide_round_up(len(button_list),4)):
            logging.info(str(index))
            line = self.create_button_line(index, button_list)
            self.button_column.add(line)
            
        ### add the row widgets to the column widget
        column.add_spacing(8)
        column.add(update_expdir_row)
        column.add_spacing(3)
        column.add(expdir_row)
        column.add_spacing(8)
        column.add(label_row)
        column.add(fields_row)
        column.add_spacing(8)
        column.add(self.button_column)
        column.add_spacing(5)
        column.add_stretch()

        # default state of export buttons:
        for button in self.button_widgets_list:
            button._widget.enabled = False
                   
        return column

    def update_button_state(self, button, **kwargs):
 
        if ('no' in kwargs):
            self.have_no = True
        elif ('sub' in kwargs):
            self.have_sub = True
        elif ('fov' in kwargs):
            self.have_fov =  True
        elif ('descr' in kwargs):
            self.have_descr = True    
        
        # No, FOV and Description are required fields
        if self.have_no and self.have_fov and self.have_descr:
            logging.info("all fields defined")
            def update():
                button._widget.enabled = True
                logging.info("have enabled button")
            # that actuale does the update
            self.__api.queue_task(update)  
 
    
    # we need several instances of this
    def create_button_line(self, index, button_list):
        logging.info(str(index))
        logging.info(str(button_list))
        logging.info("%s %s %s", (4*index)+1, (4*index)+2, (4*index)+3 )
        

        row = self.ui.create_row_widget()
        column = self.ui.create_column_widget()       

        def export_button_clicked(button_list_index):
            logging.info("button_clicked index: %s", button_list_index)
            writer = self.writer
            # button is disabled until all required (No, FOV, Descr) editable fields are filled in 
            #!!! find out whether by passing "ui" to the function we can replace the loooong __api.application.... string with "ui"        
            prefix = get_prefix_string(self.fields_no_edit.text)
            postfix = get_postfix_string(self.fields_sub_edit.text, self.fields_fov_edit.text, self.fields_descr_edit.text)
            
            ## apply new title to selected DISPLAY item
            # Demie wants selected item to be display item not data item in the panel
            item = self.__api.application.document_controllers[0]._document_controller.selected_display_item
            item.title = prefix + str(button_list[button_list_index]) + postfix
            ## save file (should we warn if already exists?)
            #directory = self.ui.get_persistent_string("export_directory", self.ui.get_document_location())
            directory = self.__api.application.document_controllers[0]._document_controller.ui.get_persistent_string('export_directory')
            logging.info("getpersistentdir %s", directory)
            filename = item.title
            extension = writer.extensions[0]
            path = os.path.join(directory, "{0}.{1}".format(filename, extension))
            logging.info("path %s", path)
            if not os.path.isdir(directory):
                os.makedirs(directory)
                logging.info("path did not exist")
            else:
                logging.info("Directory already exists")
                # launch popup dialog
            if not os.path.isfile(path):
                ImportExportManager.ImportExportManager().write_display_item_with_writer(self.__api.application.document_controllers[0]._document_controller.ui, writer, item, path)
            else:
                # launch popup dialog
                logging.info("could not export - file exists")      

        # don't know how many buttons there are, so possible to have not enough to fill a row
        try:                
            self.button1 = self.ui.create_push_button_widget(_(str(button_list[4*index])))
            row.add(self.button1)
            row.add_spacing(1)
            self.button_widgets_list.append(self.button1)
            self.button1.on_clicked = functools.partial(export_button_clicked, (4*index))     
        except IndexError:
            logging.info("Button1 %s", index)
        try:
            self.button2 = self.ui.create_push_button_widget(_(str(button_list[(4*index)+1])))
            row.add(self.button2)
            row.add_spacing(1)
            self.button_widgets_list.append(self.button2)            
            self.button2.on_clicked = functools.partial(export_button_clicked, (4*index)+1)     
        except IndexError:
            logging.info("button2 %s", index)
        try:
            self.button3 = self.ui.create_push_button_widget(_(str(button_list[(4*index)+2])))
            row.add(self.button3)
            row.add_spacing(1)
            self.button_widgets_list.append(self.button3)            
            self.button3.on_clicked = functools.partial(export_button_clicked, (4*index)+2)        
        except IndexError:
            logging.info("button3 %s", index)
        try:
            self.button4 = self.ui.create_push_button_widget(_(str(button_list[(4*index)+3])))
            row.add(self.button4)
            row.add_spacing(2)
            self.button_widgets_list.append(self.button4)                
            self.button4.on_clicked = functools.partial(export_button_clicked, (4*index)+3)          
        except IndexError:
            logging.info("Button4 %s", index)  
        row.add_stretch()    

        column.add(row)
        column.add_spacing(0)
        
        return column


        
class PanelQuickDMExportExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.examples.quickdmexport_panel"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__panel_ref = api.create_panel(PanelQuickDMExportDelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__panel_ref.close()
        self.__panel_ref = None
