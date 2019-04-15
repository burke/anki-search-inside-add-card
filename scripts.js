var selectedDecks = ["-1"];
var $hvrBox = $('#hvrBox');
var $hvrBoxSub = $('#hvrBoxSub');
var hvrBoxIndex = 0;
var hvrBoxLength = 0;
var fontSize = 12;
var hvrBoxPos = { x: 0, y: 0 };
var divTmp = document.createElement('span');
var timeout;
var boxIsDisplayed = false;
var isFrozen = false;
var searchOnSelection = true;
var searchOnTyping = true;
var useInfoBox = false;
var last = "";

function updateSelectedDecks(elem) {
    selectedDecks = [];
    let str = "";
    if (elem)
        $(elem).toggleClass("selected");
    $(".deck-list-item.selected").each(function () {
        selectedDecks.push($(this).data('id'));
        str += " " + $(this).data('id');
    });
    pycmd("deckSelection" + str);
}

function selectAllDecks() {
    $('.deck-list-item').addClass('selected');
    updateSelectedDecks();
}
function unselectAllDecks() {
    $('.deck-list-item').removeClass('selected');
    updateSelectedDecks();
}

function selectDeckWithId(did) {
    $('.deck-list-item').removeClass('selected');
    $(".deck-list-item").each(function () {
        if ($(this).data('id') == did) {
           $(this).addClass("selected");
        }
    });
    updateSelectedDecks();
}

function expandRankingLbl(elem) {
    
    if (elem.getElementsByClassName("rankingLblAddInfo")[0].offsetParent === null) {
        elem.getElementsByClassName("rankingLblAddInfo")[0].style.display = "inline";
    } else {
        elem.getElementsByClassName("rankingLblAddInfo")[0].style.display = "none";
    }
}


function expandCard(id, icn) {
    let elem = document.getElementById(id);
    if ($(elem).hasClass('expanded')) {
        $(elem).animate({ height: $(elem).height() - 80 }, 200);
        $(elem).removeClass("expanded");
        $(elem).css("padding-bottom", "25px")
        $('#i-' + $(elem).data('nid')).hide();
        $(icn).children().first().html('&#10097;');

    } else {
        $(elem).css("padding-bottom", "90px")
        $(elem).animate({ height: $(elem).height() + 80 }, 200);
        if ($('#i-' + $(elem).data('nid')).length) {
            $('#i-' + $(elem).data('nid')).fadeIn();
        } else {
            pycmd('nStats ' + $(elem).data('nid'));
        }
        $(elem).addClass("expanded");
        $(icn).children().first().html('&#10096;');

    }
}

function pinMouseLeave(elem) {
    $(elem).css('opacity', '0');
}
function pinMouseEnter(elem) {
    $(elem).css('opacity', '1');
}

function cardMouseEnter(elem, nid) {
    $(`#btnBar-${nid}`).css('opacity', '1');
}



function cardMouseLeave(elem, nid) {
    setTimeout(function () {
        if (!$('#btnBar-' + nid).is(':hover'))
            $('#btnBar-' + nid).css('opacity', '0');
        x
    }, 100);
}

function getSelectionText() {
    if (!searchOnSelection || isFrozen)
        return;
    var text = "";
    if (window.getSelection) {
        text = window.getSelection().toString();
    } else if (document.selection && document.selection.type != "Control") {
        text = document.selection.createRange().text;
    }
    if (text.length > 0)
        pycmd('fldSlctd ' + selectedDecks.toString() + ' ~ ' + text);
}

function specialSearch(mode) {
    document.getElementById("a-modal").style.display = 'none'; 
    $searchInfo.html("<span style='float: right;'>Searching</span>"); 
    pycmd(mode  + " " + selectedDecks.toString());
}


function onResize() {
    let vh = window.innerHeight * 0.01;
    // let topHeight = $('#topContainer').height();
    // let bottomHeight = $('#bottomContainer').height();
    // $('#resultsArea').css("height", `calc(var(--vh, 1vh) * 100 - ${topHeight + bottomHeight + 50}px)`);
    document.getElementById('resultsArea').style.setProperty('--vh', `${vh}px`);
}

function toggleModalLoader(show) {
}

function getWordPrecedingCaret(containerEl) {
    var precedingChunk = "", sel, range, precedingRange;
    if (window.getSelection) {
        sel = window.getSelection();
        if (sel.rangeCount > 0) {
            range = sel.getRangeAt(0).cloneRange();
            range.collapse(true);
            range.setStart(containerEl, 0);
            precedingChunk = range.toString().slice(-20);
        }
    } else if ((sel = document.selection) && sel.type != "Control") {
        range = sel.createRange();
        precedingRange = range.duplicate();
        precedingRange.moveToElementText(containerEl);
        precedingRange.setEndPoint("EndToStart", range);
        precedingChunk = precedingRange.text.slice(-20);
    }
    let spl = precedingChunk.split(" ");
    return spl[spl.length - 1];

}

function setHighlighting(elem) {
    let highlight = $(elem).is(":checked") ? "on" : "off";
    pycmd("highlight " + highlight);
}
function setTagSearch(elem) {
    let tagSearch = $(elem).is(":checked") ? "on" : "off";
    pycmd("tagSearch " + tagSearch);
}

function lastWord(text, caretPos) {
    var preText = text.substring(0, caretPos);
    if (preText.indexOf(" ") > 0) {
        var words = preText.split(" ");
        return words[words.length - 1]; //return last word
    }
    else {
        return preText;
    }
}

function getCursorCoords(input, selectionPoint) {
    var sel = window.getSelection();
    var range = sel.getRangeAt(0);
    range.insertNode(divTmp);
    let rect = divTmp.getBoundingClientRect();
    return { x: rect.left, y: rect.top };

}

function tagClick(elem) {
    if ($(elem).data('tags')) {
        $('#a-modal').show();
        pycmd('renderTags ' + $(elem).data('tags'));
        return
    }
    let name = $(elem).data('name');
    pycmd('tagClicked ' + name);
}

function fieldKeydown(event, elem) {
    if ((event.which == 32 || event.keyCode == 32) && event.ctrlKey) {
        event.preventDefault();
        displaySearchInfoBox(event, elem);
        return false;
    }

}

function synInputKeyup(event,elem) {
    if (event.keyCode == 13 && elem.value)
        pycmd("saveSynonyms " + elem.value);
}

function synonymSetKeydown(event, elem, index) {
    if (event.keyCode == 13 && elem.innerHTML.length) {
        pycmd("editSynonyms " + index + " " +  elem.innerHTML);
        event.preventDefault();
        $(elem).blur();
    }
}

function setUseInfoBox(active) {
    useInfoBox = active;
    if (!active) 
        $('.field').attr("onkeydown", "moveInHover(event, this);" + $(`.field`).attr("onkeydown")); 
    else 
        $('.field').attr("onkeydown", $(`.field`).attr("onkeydown").replace("moveInHover(event, this);", "")); 

}

function setSearchOnTyping(active) {
    searchOnTyping = active;
    if (!active) 
        $('.field').unbind('keypress', fieldKeypress);
    else
        $('.field').on('keypress', fieldKeypress);

    sendSearchOnTyping();
}

function sendSearchOnTyping() {
    let cmd = searchOnTyping ? "on" : "off";
    pycmd("searchWhileTyping " + cmd);
}
function sendSearchOnSelection() {
    let cmd = searchOnSelection ? "on" : "off";
    pycmd("searchOnSelection " + cmd);
}

function fieldKeypress(event, elem) {
    if (searchOnTyping && !boxIsDisplayed && event.keyCode != 13 && !(event.keyCode >= 37 && event.keyCode <= 40) && !event.ctrlKey) {
        if (timeout) {
            clearTimeout(timeout);
            timeout = null;
        }
        timeout = setTimeout(function () {
            sendContent(event);
        }, $del$);
    }
}

function searchMaskKeypress(event) {
    if (event.keyCode === 13)
        sendSearchFieldContent();
}

function hideHvrBox() {
    boxIsDisplayed = false;
    $hvrBox.hide();
    $hvrBoxSub.hide();
}

function moveInHover(event, elem) {

    if (!useInfoBox)
        return;

    //other keys, should hide box
    if (boxIsDisplayed && event.keyCode != 17 && event.keyCode != 13 && !(event.keyCode == 38 || event.keyCode == 40)) {
        hideHvrBox();
        return;
    }

    //enter when box is displayed
    if (boxIsDisplayed && event.keyCode == 13) {
        if ($('.hvrSelected').length && $('.hvrSelected').attr('id') == "hvrI-0") {
            event.preventDefault();
            searchFor(last);
            hideHvrBox();
            return false;
        } else if ($('.hvrSelected').length && $('.hvrSelected').attr('id') == "hvrI-1") {
            event.preventDefault();
            pycmd('tagClicked ' + last);
            hideHvrBox();
            return false;
        }
    }

    //ctrl + space  
    if (useInfoBox && (event.which == 32 || event.keyCode == 32) && event.ctrlKey) {
        event.preventDefault();
        displaySearchInfoBox(event, elem);
        return false;
    }

    //up down when box is displayed
    if (boxIsDisplayed && event.keyCode == 38 || event.keyCode == 40) {
        event.preventDefault();
        moveInsideHvrBox(event.keyCode);
    }
}

function displaySearchInfoBox(event, elem) {
    last = getWordPrecedingCaret(elem);
    let pos = getCursorCoords(elem, elem.selectionStart);
    fontSize = parseFloat(window.getComputedStyle(elem, null).getPropertyValue('font-size'));
    $hvrBox.css("left", pos.x + 3);
    $hvrBox.css("top", pos.y + fontSize + 3);
    $('#wiki').html('');
    $hvrBox.show();

    //get last word
    $('#hvrI-0').html(`<b>search</b> for <i>${last}</i>`);
    $('#hvrI-1').html(`add as <b>tag</b>: <i>${last}</i>`);
  
    hvrBoxIndex = -1; hvrBoxLength = 3;
    $('.hvrLeftItem').removeClass('hvrSelected');
    hvrBoxPos.x = pos.x; hvrBoxPos.y = pos.y;
    pycmd('wiki ' + last);
    boxIsDisplayed = true;
}

function displayInfoBoxSubMenu(index) {
    $hvrBoxSub.css("left", hvrBoxPos.x + 231);
    $hvrBoxSub.css("top", hvrBoxPos.y + 5 + (21 * (index + 1)));
    $hvrBoxSub.show();
}


function pinCard(elem, nid) {
    $('#cW-' + nid).css('padding', '3px 4px 5px 5px');
    $('#cW-' + nid).css('font-size', '10px');
    let info = document.getElementById('cW-' + nid).getElementsByClassName("rankingLblAddInfo")[0];
    $('#cW-' + nid).html('<span>&#128204;</span>');
    document.getElementById('cW-' + nid).appendChild(info);
    $('#' + nid).parents().first().addClass('pinned');
    updatePinned();
}

function searchCard(elem) {
    let html = $(elem).parent().next().html();
    pycmd('fldChgd ' + selectedDecks.toString() + ' ~ ' + html);
}

function edit(nid) {
    pycmd('editN ' +  nid);
}

function updatePinned() {
    let pincmd = 'pinCrd';
    $('.pinned').each(function (index) {
        pincmd += " " + $(this).children().first().attr('id').substring(3);
    });
    pycmd(pincmd);
}

function setSearchResults(html, infoStr) {
    $('.cardWrapper').not('.pinned').remove();
    document.getElementById('searchInfo').innerHTML = infoStr;
    document.getElementById('searchResults').innerHTML += html;
    document.getElementById('searchResults').scrollTop = 0;
}

function moveInsideHvrBox(keyCode) {
    if (keyCode == 38 && hvrBoxIndex > 0) {
        document.getElementById('hvrI-' + hvrBoxIndex).className = 'hvrLeftItem';
        document.getElementById('hvrI-' + (hvrBoxIndex - 1)).className += ' hvrSelected';
        hvrBoxIndex -= 1;

    } else if (keyCode == 40 && hvrBoxLength - 1 > hvrBoxIndex) {
        if (hvrBoxIndex >= 0)
            document.getElementById('hvrI-' + hvrBoxIndex).className = 'hvrLeftItem';
        document.getElementById('hvrI-' + (hvrBoxIndex + 1)).className += ' hvrSelected';
        hvrBoxIndex += 1;

    }
    if (hvrBoxIndex == 2) {
        displayInfoBoxSubMenu(2);
        pycmd("lastnote");
    }
    else
        $hvrBoxSub.hide();

}


function toggleTooltip(elem) {
    $(elem).children().first().toggle();
}

function toggleFreeze(elem) {
    isFrozen = ! isFrozen;
    if ($(elem).hasClass('frozen')) {
        $(elem).removeClass('frozen');
        $(elem).html("FREEZE &#10052;");
    } else {
        $(elem).addClass('frozen');
        $(elem).html("FROZEN &#10052;");
    }
}


function toggleTop(elem) {
    $('#topContainer').toggle();
    if ($('#topContainer').is(":hidden")) {
        $('#resultsArea').css('height', 'calc(var(--vh, 1vh) * 100 - $h-1$px)').css('border-top', '0px');
        $(elem).children().first().html('&#10097;');
        pycmd("toggleTop off");

    } else {
        $('#resultsArea').css('height', 'calc(var(--vh, 1vh) * 100 - $h-2$px)').css('border-top', '1px solid grey');;
        $(elem).children().first().html('&#10096;');
        pycmd("toggleTop on");
    }
}





