    # to replace switch_project_reference in Application.py in site-packages/Nion/swift/Application.py

    def switch_project_reference(self, project_reference: Profile.ProjectReference) -> None:
        
        ### DMH 231122
        ### adding hook to update sstem_current_project_dir and sstem_last_project_dir variable in persistent config file
        ### whenever a project is loaded
        profile = self.profile
        ## re-set last project dir (what was sstem_current_project_dir is pushed onto sstem_last_project_dir)
        sstem_last_project_dir = self.ui.get_persistent_string("sstem_current_project_dir")
        # writing the last project to persistent config
        self.ui.set_persistent_string("sstem_last_project_dir",sstem_last_project_dir)
        #logging.info("switch proj ref last %s", sstem_last_project_dir)
        ## re-set current project dir (project_reference is pushed onto sstem_current_project_dir)
        sstem_current_project_dir = str(project_reference.project_path).rsplit("/",1)[0]
        # writing the current project to persistent config
        self.ui.set_persistent_string("sstem_current_project_dir",sstem_current_project_dir)
        #logging.info("switch proj ref current %s", sstem_current_project_dir)
        ### DMH END

        for window in self.windows:
            if isinstance(window, DocumentController.DocumentController):
                window.request_close()
        try:
            self.open_project_window(project_reference)
        except Exception:
            self.show_ok_dialog(_("Error Opening Project"), _("Unable to open project."), completion_fn=self.show_choose_project_dialog)

