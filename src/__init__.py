#!/usr/bin/env python
# -*- coding: utf-8 -*-
from aqt import mw, dialogs
from aqt.utils import showInfo
from aqt.qt import *
from anki.hooks import runHook, addHook, wrap
import aqt
import aqt.webview
from aqt.addcards import AddCards
import aqt.editor
from aqt.editor import Editor, EditorWebView
from aqt.browser import Browser
from aqt.tagedit import TagEdit
from aqt.editcurrent import EditCurrent
import aqt.stats
from aqt.main import AnkiQt
from aqt.webview import AnkiWebPage
from datetime import datetime
import os
import random
import sqlite3
import re
import time as t
import math
import webbrowser
import platform
import functools
import sys
import html
sys.path.insert(0, os.path.dirname(__file__))


from .state import checkIndex, get_index, set_index, corpus_is_loaded, set_corpus, set_edit, get_edit, set_old_on_bridge_cmd
from .indexing import build_index, get_notes_in_collection
from .debug_logging import log
from .web.web import printStartingInfo, getScriptPlatformSpecific, showSearchResultArea, fillDeckSelect, fillTagSelect
from .web.html import rightSideHtml
from .notes import *
from .output import Output
from .editor import EditDialog
from .tag_find import findBySameTag, display_tag_info, get_most_active_tags
from .command_parsing import expanded_on_bridge_cmd, addHideShowShortcut, addNoteAndUpdateIndex, rerenderNote

config = mw.addonManager.getConfig(__name__)


delayWhileTyping = max(500, config['delayWhileTyping'])


def initAddon():
    global oldOnBridge, origAddNote, origTagKeypress, origSaveAndClose, origEditorContextMenuEvt
    
    set_old_on_bridge_cmd(Editor.onBridgeCmd)
    Editor.onBridgeCmd = expanded_on_bridge_cmd
    #todo: Find out if there is a better moment to start index creation
    addHook("profileLoaded", build_index)
    origAddNote = AddCards.addNote
    origEditorContextMenuEvt = EditorWebView.contextMenuEvent

    AddCards.addNote = addNoteAndUpdateIndex
    origTagKeypress = TagEdit.keyPressEvent
    TagEdit.keyPressEvent = tagEditKeypress
     
    setupTagEditTimer()
    EditorWebView.contextMenuEvent = editorContextMenuEventWrapper

    origSaveAndClose = EditDialog.saveAndClose
    EditDialog.saveAndClose = editorSaveWithIndexUpdate

    addHook("setupEditorShortcuts", addHideShowShortcut)
   
    #dialogs._dialogs["UserNoteEditor"] = [NoteEditor, None]


    #main functions to search
    if not config["disableNonNativeSearching"]:
        aqt.editor._html += """
            <script>
            function sendContent(event) {
                if ((event && event.repeat) || isFrozen)
                    return;
                let html = "";
                showLoading("Typing");
                $fields.each(function(index, elem) {
                    html += $(elem).html() + "\u001f";
                });
                pycmd('fldChgd ' + selectedDecks.toString() + ' ~ ' + html);
            }
            function sendSearchFieldContent() {
                showLoading("Browser Search");
                html = $('#searchMask').val() + "\u001f";
                pycmd('srchDB ' + selectedDecks.toString() + ' ~ ' + html);
            }

            function searchFor(text) {
                showLoading("Note Search");
                text += "\u001f";
                pycmd('fldChgd ' + selectedDecks.toString() + ' ~ ' + text);
            }
            </script>
        """
    else:
        aqt.editor._html += """
            <script>
            function sendContent(event) {
                return;
            }
            function sendSearchFieldContent() {
                showLoading("Note Search");
                html = $('#searchMask').val() + "\u001f";
                pycmd('srchDB ' + selectedDecks.toString() + ' ~ ' + html);
            }

            function searchFor(text) {
                return;
            }
            </script>
        """

    #this inserts all the javascript functions in scripts.js into the editor webview
    aqt.editor._html += getScriptPlatformSpecific(config["addToResultAreaHeight"], delayWhileTyping)
    #when a note is loaded (i.e. the add cards dialog is opened), we have to insert our html for the search ui
    addHook("loadNote", onLoadNote)


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback) 
    sys.exit(1) 
   


def editorSaveWithIndexUpdate(dialog):
    origSaveAndClose(dialog)
    # update index
    searchIndex = get_index()
    if searchIndex is not None and dialog.editor is not None and dialog.editor.note is not None:
        searchIndex.updateNote(dialog.editor.note)
        # note should be rerendered
        rerenderNote(dialog.editor.note.id)
         # keep track of edited notes (to display a little remark in the results)
        searchIndex.output.edited[str(dialog.editor.note.id)] = t.time()
 

def onLoadNote(editor):
    """
    Executed everytime a note is created/loaded in the add cards dialog.
    Wraps the normal editor html in a flex layout to render a second column for the searching ui.
    """
    config = mw.addonManager.getConfig(__name__)

    #only display in add cards dialog or in the review edit dialog (if enabled)
    if editor.addMode or (config["useInEdit"] and isinstance(editor.parentWindow, EditCurrent)):
        searchIndex = get_index()
        if searchIndex is not None and searchIndex.logging:
            log("Trying to insert html in editor")
            log("Editor.addMode: %s" % editor.addMode)

        editor.web.eval("var addToResultAreaHeight = %s; var showTagInfoOnHover = %s; tagHoverTimeout = %s;" % (
            config["addToResultAreaHeight"], 
            "true" if config["showTagInfoOnHover"] and config["noteScale"] == 1.0 else "false", 
            config["tagHoverDelayInMiliSec"]
            ))

        # render the right side (search area) of the editor
        # (the script checks if it has been rendered already)
        editor.web.eval(rightSideHtml(config, searchIndex is not None))


        if searchIndex is not None:
            showSearchResultArea(editor)
            #restore previous settings
            if not searchIndex.highlighting:
                editor.web.eval("$('#highlightCb').prop('checked', false);")
            if not searchIndex.searchWhileTyping:
                editor.web.eval("$('#typingCb').prop('checked', false); setSearchOnTyping(false);")
            if not searchIndex.searchOnSelection:
                editor.web.eval("$('#selectionCb').prop('checked', false);")
            if not searchIndex.tagSearch:
                editor.web.eval("$('#tagCb').prop('checked', false);")
            if searchIndex.tagSelect:
                fillTagSelect(editor)
            if not searchIndex.topToggled:
                editor.web.eval("hideTop();")
            if searchIndex.output is not None and not searchIndex.output.uiVisible:
                editor.web.eval("$('#infoBox').addClass('addon-hidden')")
            if config["gridView"]:
                editor.web.eval('activateGridView();')
            if searchIndex.output is not None:
                #plot.js is already loaded if a note was just added, so this is a lazy solution for now
                searchIndex.output.plotjsLoaded = False
                
        editor.web.eval("onResize()")


        if searchIndex is None or not searchIndex.tagSelect:
            fillDeckSelect(editor)
            if get_index() is None or searchIndex.lastSearch is None:
                printStartingInfo(editor)
        if not corpus_is_loaded():
            if searchIndex is not None and searchIndex.logging:
                log("loading notes from anki db...")
            corpus = get_notes_in_collection()
            set_corpus(corpus)
            if searchIndex is not None and searchIndex.logging:
                log("loaded notes: len(corpus): " + str(len(corpus)))

        if searchIndex is not None and searchIndex.output is not None:
            searchIndex.output.editor = editor
            searchIndex.output._loadPlotJsIfNotLoaded()
    if get_edit() is None and editor is not None:
        set_edit(editor)



   
    

def editorContextMenuEventWrapper(view, evt):
    global contextEvt
    win = aqt.mw.app.activeWindow()
    if isinstance(win, Browser):
        origEditorContextMenuEvt(view, evt)
        return
    contextEvt = evt
    pos = evt.pos()
    determineClickTarget(pos)
    #origEditorContextMenuEvt(view, evt)

def determineClickTarget(pos):
    if not checkIndex():
        return
    get_index().output.editor.web.page().runJavaScript("sendClickedInformation(%s, %s)" % (pos.x(), pos.y()), addOptionsToContextMenu)

def addOptionsToContextMenu(clickInfo):
    searchIndex = get_index()
    
    if clickInfo is not None and clickInfo.startswith("img "):
        try:
            src = clickInfo[4:]
            m = QMenu(searchIndex.output.editor.web)
            a = m.addAction("Open Image in Browser")
            a.triggered.connect(lambda: openImgInBrowser(src))
            cpSubMenu = m.addMenu("Copy Image To Field...")
            for key in searchIndex.output.editor.note.keys():
                cpSubMenu.addAction("Append to %s" % key).triggered.connect(functools.partial(appendImgToField, src, key))
            m.popup(QCursor.pos())
        except:
            origEditorContextMenuEvt(searchIndex.output.editor.web, contextEvt)
    elif clickInfo is not None and clickInfo.startswith("note "):
        try:
            content = " ".join(clickInfo.split()[2:])
            nid = int(clickInfo.split()[1])
            m = QMenu(searchIndex.output.editor.web)
            a = m.addAction("Find Notes Added On The Same Day")
            a.triggered.connect(lambda: getCreatedSameDay(searchIndex, searchIndex.output.editor, nid))
            m.popup(QCursor.pos())
        except:
            origEditorContextMenuEvt(searchIndex.output.editor.web, contextEvt)
            
    # elif clickInfo is not None and clickInfo.startswith("span "):
    #     content = clickInfo.split()[1]
        
    else: 
        origEditorContextMenuEvt(searchIndex.output.editor.web, contextEvt)




def openImgInBrowser(url):
    if len(url) > 0:
        webbrowser.open(url)

def appendNoteToField(content, key):
    if not checkIndex():
        return
    searchIndex = get_index()
    note = searchIndex.output.editor.note
    note.fields[note._fieldOrd(key)] += content
    note.flush()
    searchIndex.output.editor.loadNote()

def appendImgToField(src, key):
    if not checkIndex() or src is None or len(src) == 0:
        return
    searchIndex = get_index()
    note = searchIndex.output.editor.note
    src = re.sub("https?://[0-9.]+:\\d+/", "", src)
    note.fields[note._fieldOrd(key)] += "<img src='%s'/>" % src
    note.flush()
    searchIndex.output.editor.loadNote()


       
def setupTagEditTimer():
    global tagEditTimer
    tagEditTimer = QTimer() 
    tagEditTimer.setSingleShot(True) # set up your QTimer


def tagEditKeypress(self, evt):
    """
    Used if "search on tag entry" is enabled.
    Triggers a search if the user has stopped typing in the tag field.
    """
    origTagKeypress(self, evt)
    win = aqt.mw.app.activeWindow()
    # dont trigger keypress in edit dialogs opened within the add dialog
    if isinstance(win, EditDialog) or isinstance(win, Browser):
        return
    searchIndex = get_index()

    if searchIndex is not None and searchIndex.tagSearch and len(self.text()) > 0:
        text = self.text()
        try: 
            tagEditTimer.timeout.disconnect() 
        except Exception: pass
        tagEditTimer.timeout.connect(lambda: rerenderInfo(searchIndex.output.editor, text, searchByTags = True))  # connect it to your update function
        tagEditTimer.start(1000)    




initAddon()