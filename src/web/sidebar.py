import typing
from typing import List, Optional, Tuple, Any
from aqt.editor import Editor
from anki.utils import isMac, isLin

from ..notes import get_note, _get_priority_list, get_avg_pages_read, get_all_tags, get_related_notes, get_priority_as_str, get_notes_scheduled_for_today
from ..config import get_config_value_or_default as conf_or_def
from .templating import filled_template
import utility.misc
import utility.tags
import utility.text

class Sidebar:
    """ The toggle-able sidebar that is displayed left of the results. """

    def __init__(self):

        self.ADDON_NOTES_TAB        : int       = 1
        self.PDF_IMPORT_TAB         : int       = 2
        self.SPECIAL_SEARCHES_TAB   : int       = 3

        self.tab                    : int       = self.ADDON_NOTES_TAB
        self._editor                : Editor    = None

    def set_editor(self, editor: Editor):
        self._editor = editor

    def _html(self) -> str:

        tab_displayed_name = self._tab_displayed_name()

        if self.tab == self.ADDON_NOTES_TAB:
            tags = get_all_tags()
            tmap = utility.tags.to_tag_hierarchy(tags)

            def iterateMap(tmap, prefix, start=False):
                if start:
                    html = "<ul class='deck-sub-list outer'>"
                else:
                    html = "<ul class='deck-sub-list'>"
                for key, value in tmap.items():
                    full = prefix + "::" + key if prefix else key
                    html += "<li class='deck-list-item' onclick=\"event.stopPropagation(); searchUserNoteTag(event, '%s');\"><div class='list-item-inner'><b class='exp'>%s</b> %s <span class='siac-tl-plus' onclick='event.stopPropagation(); pycmd(\"siac-create-note-tag-prefill %s\") '><b> + &nbsp;</b></span></div>%s</li>" % (full, "[+]" if value else "", utility.text.trim_if_longer_than(key, 35), full, iterateMap(value, full, False))
                html += "</ul>"
                return html

            tag_html            = iterateMap(tmap, "", True)
            tag_len             = len(tmap) if tmap is not None else 0

            # check if there are any notes scheduled for today
            scheduled_for_today = get_notes_scheduled_for_today()
            if scheduled_for_today is not None and len(scheduled_for_today) > 0:
                sched_today_menu_item = f"""<div class='siac-notes-sidebar-item blue-hover' onclick='pycmd("siac-r-show-due-today")'>Due today ({len(scheduled_for_today)})</div>"""
            else:
                sched_today_menu_item = ""

            tab_html = filled_template("sidebar_addon_tab", dict(sched_today_menu_item = sched_today_menu_item, tag_len = tag_len, tag_html = tag_html))

        elif self.tab == self.PDF_IMPORT_TAB:

            folders_to_search = conf_or_def("pdf.import.folders_to_search", [])
            exp = ""
            if len(folders_to_search) == 0:
                folders = """
                    <center style='margin-top: 100px;'>
                        <strong>
                            To browse local folders for pdfs, add some entries to the config option
                            "pdf.import.folders_to_search", e.g. <br><br>
                            "pdf.import.folders_to_search" : ["Some/Path/Documents/Uni", "Some/Path/Documents/Unsorted"] <br><br>
                            
                            The given folders (including their subfolders!) will be scanned for *.pdf files.
                            Don't use too large folders here, because they are searched everytime the tab is opened so you might see a delay then. 
                        </strong>
                    </center>
                """
            else:
                cleaned = []
                for f in folders_to_search:
                    if len(f.strip()) == 0:
                        continue
                    cleaned.append(f.replace("\\", "/"))
                if len(cleaned) == 0:
                    folders = """
                    <center style='margin-top: 100px;'>
                        <strong>
                            Could not find any pdf files in the specified folders.
                        </strong>
                    </center>
                    """
                else:
                    files = []
                    for f in cleaned:
                        files += utility.misc.find_pdf_files_in_dir_recursive(f, cut_path=False)
                    
                    map = utility.tags.to_tag_hierarchy(files, sep="/")
                    map = utility.tags.flatten_map(map, "/")
                    def iterateMap(tmap, prefix, start=False):
                        if start:
                            html = "<ul class='deck-sub-list outer'>"
                        else:
                            html = "<ul class='deck-sub-list'>"
                        for key, value in tmap.items():
                            full        = prefix + "/" + key if prefix else key
                            if isMac or isLin and not full.startswith("/"):
                                full = f"/{full}"
                            click       = f"pycmd(\"siac-create-note-source-prefill {full}\")" if full.endswith(".pdf") else ""
                            exp         = "[+]" if value else ""
                            should_bold = "style='font-weight: bold;'" if value else ""
                            html        = f"{html}<li class='deck-list-item' onclick='event.stopPropagation(); {click}'><div class='list-item-inner' {should_bold}><b class='exp'>{exp}</b> {utility.text.trim_if_longer_than(key, 35)}</div>{iterateMap(value, full, False)}</li>"
                        html += "</ul>"
                        return html
                    folders = iterateMap(map, "", True)
                    folders = f"""<div style='margin-top: 15px;'>
                        {folders} 
                    </div>"""
                    exp = f"""
                        <div class='mr-5 mb-5' style='flex: 0 1 auto; padding-right: 5px;'>
                            <div class='w-100' style='margin-top: 20px;'><b>PDFs in Folders</b>
                                <b class='siac-tags-exp-icon' style='margin-right: 15px; padding: 0 2px 0 2px;' onclick='noteSidebarCollapseAll();'>&#x25B2;</b>
                                <b class='siac-tags-exp-icon mr-5' style='padding: 0 2px 0 2px;' onclick='noteSidebarExpandAll();'>&#x25BC;</b>
                            </div>
                        </div>
                    """

            tab_html = f"""
                {exp}
                <div class='mr-5 mb-5' style='flex: 1 1 auto; padding-right: 5px; overflow-y: auto;'>
                    {folders}
                </div>
            """

        elif self.tab == self.SPECIAL_SEARCHES_TAB:

            tab_html = filled_template("sidebar_anki_tab", {})

        return filled_template("sidebar", dict(tab_html = tab_html, tab_displayed_name = tab_displayed_name))

    def display(self):
        html = self._html()
        self._editor.web.eval("""
        if (!document.getElementById('siac-notes-sidebar')) {
            document.getElementById('resultsWrapper').insertAdjacentHTML("afterbegin", `%s`); 
            $('#siac-notes-sidebar .exp').click(function(e) {
                e.stopPropagation();
                let icn = $(this);
                if (icn.text()) {
                    if (icn.text() === '[+]')
                        icn.text('[-]');
                    else
                        icn.text('[+]');
                }
                $(this).parent().parent().children('ul').toggle();
            });
        }
        """ % html)

    def hide(self):
        self._editor.web.eval("$('#siac-notes-sidebar').remove(); $('#resultsWrapper').css('padding-left', 0);")

    def refresh_tab(self, tab: int):
        if self.tab == tab:
            self.refresh()

    def refresh(self):
        html = self._html()
        self._editor.web.eval("""
            if (document.getElementById('siac-notes-sidebar')) {
                $('#siac-notes-sidebar').remove();
                document.getElementById('resultsWrapper').insertAdjacentHTML("afterbegin", `%s`); 
                $('#siac-notes-sidebar .exp').click(function(e) {
                e.stopPropagation();
                let icn = $(this);
                if (icn.text()) {
                    if (icn.text() === '[+]')
                        icn.text('[-]');
                    else
                        icn.text('[+]');
                }
                $(this).parent().parent().children('ul').toggle();
                });
            }
        """ % html)
    

    def show_tab(self, tab: int):
        self.tab = tab
        self.refresh()


    def _tab_displayed_name(self) -> str:
        if self.tab == self.PDF_IMPORT_TAB:
            return "PDF Import"
        elif self.tab == self.ADDON_NOTES_TAB:
            return "Add-on Notes"
        elif self.tab == self.SPECIAL_SEARCHES_TAB:
            return "Anki Notes"