from aqt import mw
import time


def findNotesWithLowestPerformance(decks, limit, retOnly = False):
    #avgRetAndTime = getAvgTrueRetentionAndTime()
    if not "-1" in decks:
        deckQ =  "(%s)" % ",".join(decks)
    else:
        deckQ = ""
    if deckQ:
        notes = mw.col.db.execute("select notes.id, cards.id, flds, tags, did from cards left join notes on cards.nid = notes.id where did in %s order by notes.id" % deckQ).fetchall()
    else:
        notes = mw.col.db.execute("select notes.id, cards.id, flds, tags, did from cards left join notes on cards.nid = notes.id order by notes.id ").fetchall()
    scores = dict()
    cardsByNotes = dict()
    for note in notes:
        if note[0] in cardsByNotes:
            cardsByNotes[note[0]][1].append(note[1])
        else:
            cardsByNotes[note[0]] = (note, [note[1]])
    for k,v in cardsByNotes.items():
        score = _getScore(v[1], retOnly)
        if score is not None:
            if retOnly:
                    scores[k] = (score, v[0]) 
            else:
                scores[k] = (score[0], v[0]) 
    scores = sorted(scores.items(), key=lambda x: x[1][0], reverse=False)
    rList = []
    for r in scores[:limit]:
        rList.append((r[1][1][2], r[1][1][3],r[1][1][4], r[1][1][0]))
    return rList


def getAvgTrueRetentionAndTime():
    eases = mw.col.db.all("select ease, time from revlog where type = 1")
    if not eases:
        return 0
    cnt = 0
    passed = 0
    failed = 0
    timeTaken = 0
    for ease, taken in eases:
        cnt += 1
        if ease != 1:
            passed += 1
        else:
            failed += 1
        timeTaken += taken / 1000.0
    retention = 100 * passed / (passed + failed) if cnt > 0 else 0
    retention = round(retention, 2)
    return (round(retention,1), round(timeTaken / cnt, 1))

def calcAbsDiffInPercent(i1, i2):
    diff = round(i1 - i2, 2)
    if diff >= 0:
        return "+ " + str(diff)
    else:
        return str(diff)


def _getScore(cards, onlyRet = False):
    if not cards:
        return None
    cStr = "("
    for c in cards:
        cStr += str(c) + ", "
    cStr = cStr[:-2] + ")"

    entries = mw.col.db.all( "select cid, ease, time, type from revlog where cid in %s" %(cStr))
    if not entries:
        return None
    cnt = 0
    passed = 0
    failed = 0
    goodAndEasy = 0
    hard = 0
    timeTaken = 0
    for (cid, ease, taken, ty) in reversed(entries):
        #only look for reviews
        if ty != 1:
            continue
        cnt += 1
        if ease != 1:
            passed += 1
            if ease == 2:
                hard += 1
            else:
                goodAndEasy += 1
        else:
            failed += 1
        
        timeTaken += taken  / 1000.0    
    if cnt <= 3:
        return None
    retention =  100 * passed / (passed + failed)
    retention = round(retention, 1)
    if onlyRet:
        return retention
    avgTime = round(timeTaken / cnt, 1)
    return _calcPerformanceScore(retention, avgTime, goodAndEasy, hard)


def calculateStats(nid, gridView):
    
    tables = []
    infoTable = {}
    infoTable["Note ID"] = nid

    note = mw.col.getNote(nid)
    model = mw.col.models.get(note.mid)
    templates = mw.col.findTemplates(note)

    try:
        infoTable["Created Date"] = time.strftime("%Y-%m-%d", time.localtime(int(nid)/1000)) + " &nbsp;&nbsp;<a href='#' style='' onclick='pycmd(\"addedSameDay %s\"); $(\"#a-modal\").hide(); return false;'>Added Same Day</a>" % nid
        infoTable["Last Modified"] = time.strftime("%Y-%m-%d", time.localtime(note.mod))
    except:
        pass
    if model is not None:
        infoTable["Note Type"] = model["name"]


    #get card ids for note
    cards = mw.col.db.all("select * from cards where nid = %s" %(nid))
    if not cards:
        infoTable["Result"] = "No cards found"
        tables.append(infoTable)
        return _buildTable(tables)
    cardOrdById = {}
    cardTypeById = {}
    cStr = "("
    for c in cards:
        cStr += str(c[0]) + ", "
        cardOrdById[c[0]] = c[3]
        cardTypeById[c[0]] = _cardTypeStr(c[6])
    cStr = cStr[:-2] + ")"
    
    cardNameById = {}
    for k,v in cardOrdById.items():
        for temp in templates:
            if temp['ord'] == v:
                cardNameById[k] = temp['name']



    entries = mw.col.db.all("select id, cid, ease, ivl, time, type from revlog where cid in %s" %(cStr))

    hasReview = False
    if entries:
        for (_, _, _, _, _, ty) in entries:
                if ty == 1:
                    hasReview = True
                    break
    
    reviewPlotData = {}
   
    if not entries or not hasReview:
        infoTable["Result"] = "No cards have been reviewed yet for this note"
        tables.append(infoTable)
    else:
        cnt = 0
        passed = 0
        failed = 0
        easy = 0
        goodAndEasy = 0
        good = 0
        hard = 0
        timeTaken = 0
        intervalsByName = {}
        for (stamp, cid, ease, ivl, taken, ty) in entries:
            #only look for reviews
            if ty != 1:
                continue
            cnt += 1
            intervalsByName[cardNameById[cid]] = ivl
            if not cardNameById[cid] in reviewPlotData:
                reviewPlotData[cardNameById[cid]] = []
            reviewPlotData[cardNameById[cid]].append([cnt, ease, time.strftime("%Y-%m-%d", time.localtime(int(stamp)/1000))])
            if ease != 1:
                passed += 1
                if ease == 2:
                    hard += 1
                else:
                    goodAndEasy += 1
                    if ease == 3:
                        good += 1
                    else:
                        easy += 1
            else:
                failed += 1
            
            timeTaken += taken  / 1000.0 
       
         
        retention =  100 * passed / (passed + failed) if cnt > 0 else 0
        retention = round(retention, 1)
        avgTime = round(timeTaken / cnt, 1) if cnt > 0 else 0
        score = _calcPerformanceScore(retention, avgTime, goodAndEasy, hard) if cnt > 0 else (0, 0, 0, 0)
        tables.append(infoTable)
        infoTable = {}        
        
        infoTable["Cards Found"] = len(cards)
        tables.append(infoTable)
        
        for k,v in cardNameById.items():
            infoTable = {}
            infoTable["<b>%s</b>:" % v] = ""
            if v in intervalsByName:
                infoTable["Interval"] = "%s %s" % (abs(intervalsByName[v]), "Days" if intervalsByName[v] > 0 else "Seconds")
            if k in cardTypeById:
                infoTable["Type"] = cardTypeById[k]
            tables.append(infoTable)

      
        infoTable = {}
        infoTable["Reviews (Cards from this note)"] = cnt
        infoTable["Reviews - <span style='color: red'>Failed</span>"] = failed
        infoTable["Reviews - <span style='color: black'>Hard</span>"] = hard
        infoTable["Reviews - <span style='color: green'>Good</span>"] = good
        infoTable["Reviews - <span style='color: blue'>Easy</span>"] = easy
        tables.append(infoTable)

      

        if cnt > 0:
            avgRetAndTime = getAvgTrueRetentionAndTime()
            infoTable = {}
            infoTable["True Retention (Cards from this note)"] = retention
            infoTable["True Retention (Collection)"] = avgRetAndTime[0]
            infoTable["True Retention (Difference)"] =  str(calcAbsDiffInPercent(retention, avgRetAndTime[0])) + "%"
            tables.append(infoTable)    

            infoTable = {}
            infoTable["Average Time (Cards from this note)"] = avgTime
            infoTable["Average Time (Collection)"] = avgRetAndTime[1]
            infoTable["Average Time (Difference)"] = str(calcAbsDiffInPercent(avgTime, avgRetAndTime[1])) + "s"
            tables.append(infoTable)
           

        infoTable = {}
        infoTable["Retention Score"] = score[2]
        infoTable["Time Score"] = score[1]
        infoTable["Rating Score"] = score[3]
        infoTable["-> Performance"] = score[0]
        tables.append(infoTable)
    
    return( _buildTable(tables, reviewPlotData), reviewPlotData)


def _buildTable(tables, reviewPlotData):
    s = "<div style='width: calc(100%% - 5px); overflow-y: auto; padding-right: 5px;'><table style='width: 100%%; margin-bottom: 5px;'>%s </table></div>" 
    rows = ""
    for table in tables:     
        for key, value in table.items():
            rows += "<tr><td>%s</td><td>%s</td></tr>" % (key, value)
        rows += "<tr><td>&nbsp;</td><td>&nbsp;</td></tr>"
    c = 0
    s = s % rows
    for k,v in reviewPlotData.items(): 
        if len(v) > 1:
            c+= 1
            s += "<div><h3 style='margin-top: 10px;'>%s:</h3>" % k
            s += "<div id='graph-" + str(c) + "' style='width: 96%; height: 300px; margin-top: 5px; margin-bottom: 40px;'></div></div>"

    return s


def _cardTypeStr(typeNumber):
    if typeNumber == 0:
        return "new"
    if typeNumber == 1:
        return "learning"
    if typeNumber == 2:
        return "due"
    if typeNumber == 3:
        return "filtered"
    return "?"


def _calcPerformanceScore(retention, time, goodAndEasy, hard):
    if goodAndEasy == 0 and hard == 0:
        return (0,0,0,0)
    #retention is counted higher, numbers are somewhat arbitrary
    score = 0
    retentionSc = 2 * retention * (1 - ((100 - retention) / 100))
    score += retentionSc
    timeSc = 100.0 - time / 3.0  * 10.0
    if timeSc < 0:
        timeSc = 0
    score += timeSc
    ratingSc = (goodAndEasy / (goodAndEasy + hard)) * 100
    score += ratingSc
    score = round(score * 100.0 / 400.0, 1)
    return (int(score), int(timeSc), int(retentionSc * 100.0 / 200.0), int(ratingSc)) 