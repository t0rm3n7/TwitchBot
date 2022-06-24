import sqlite3
from sqlite3 import Error
import re


class NootVsDoot:
    # teams should follow format [noot, doot, etc]
    debug = 0
    defaultTeamsDict = {
        "noot": {
            "name": "noot",
            "total": 0,
            "value": 1225,
            "captain": ""
        },
        "doot": {
            "name": "doot",
            "total": 0,
            "value": 1224,
            "captain": ""
        },
        "third": {
            "name": None,
            "total": 0,
            "value": 1226,
            "captain": ""
        }
    }
    defaultViewerDict = {
        "id": 0,
        "team": "",
        "noots": 0,
        "doots": 0,
        "third": 0,
        "captainPoints": 0
    }
    teamsDict = {}
    active = False
    channelCache = {
        "test": {
            "name": "test",
            "id": "0"
        }
    }
    dbConnection = ""

    def __init__(self):
        self.dbConnection = self.create_connection(".\\TwitchBot.sqlite")
        print("noot init")

    def cacheChannel(self, channelName):
        if self.debug == 1:
            print("attempting to cache channel name")
        selectNVD = "SELECT * FROM ChannelList " \
                    "WHERE channelName = ?"
        NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if NVDList:
            if self.debug == 1:
                print("found channel in DB")
            channelNVD = NVDList[0]
            self.channelCache.update({channelName: {"name": channelNVD[1], "id": channelNVD[0]}})
            self.teamsDict.update({channelName: dict(self.defaultTeamsDict)})
            if self.debug == 1:
                print(f"Cached channel from DB: {self.channelCache}")
        else:
            if self.debug == 1:
                print("channel not found in DB")
            insertNVD = "INSERT INTO ChannelList (channelName) " \
                        "VALUES (?)"
            self.execute_write_query(self.dbConnection, insertNVD, (channelName,))
            selectNVD = "SELECT * FROM ChannelList " \
                        "WHERE channelName = ?"
            NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
            if NVDList:
                channelNVD = NVDList[0]
                self.channelCache.update({channelName: {"name": channelNVD[1], "id": channelNVD[0]}})
                self.teamsDict.update({channelName: dict(self.defaultTeamsDict)})
                if self.debug == 1:
                    print(f"Cached channel and inserted: {self.channelCache}")
            else:
                print(
                    "Tried to add " + channelName + " to the Channel List DB, but it failed. Problems will probably "
                    "arise.")

    def isActive(self, channelName):
        # returns Active column from DB for channelName
        NVDList = self.currentStats(channelName)
        return NVDList[0][2]

    def isThird(self, channelName):
        # returns Third team name and bit total for channelName
        NVDList = self.currentStats(channelName)
        # print(NVDList[0])
        if NVDList[0][6] and NVDList[0][7]:
            return NVDList[0][6], NVDList[0][7]
        else:
            return None, None

    def currentStats(self, channelName):
        # looks up Noot vs Doot info for channelName
        selectNVD = "SELECT * from NootVsDootMain " \
                    "INNER JOIN ChannelList cl USING(channelID) " \
                    "WHERE cl.channelName = ?"
        NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName, ))
        return NVDList

    def currentPlaces(self, channelName):
        # looks up place order for Noot vs Doot
        sortDict = sorted(self.teamsDict[channelName].items(), key=lambda x: x[1]["total"], reverse=True)
        # print(sortDict)
        winningTeamDict = dict(sortDict[0][1])
        secondTeamDict = dict(sortDict[1][1])
        thirdTeamDict = dict(sortDict[2][1])
        return [winningTeamDict, secondTeamDict, thirdTeamDict]

    def determineWinner(self, channelName):
        placeDictList = self.currentPlaces(channelName)
        winningTeamDict = dict(placeDictList[0])
        secondTeamDict = dict(placeDictList[1])
        thirdTeamDict = dict(placeDictList[2])
        winningTeamName = winningTeamDict["name"].capitalize()
        secondTeamName = secondTeamDict["name"].capitalize()
        if winningTeamDict["total"] == secondTeamDict["total"] and winningTeamDict["total"] == thirdTeamDict["total"]:
            return "Noot vs Doot is over! We have a three way tie as the result! The war for Christmas has reached a " \
                   "cease-fire for now, but they will be back to settle the score!"
        elif winningTeamDict["total"] == secondTeamDict["total"] and winningTeamDict["total"] != thirdTeamDict["total"]:
            return "Noot vs Doot is over! We have a tie as the result! Congrats to Team " + winningTeamName + \
                   " and Team " + secondTeamName + " for reaching this stalemate. Come back next Christmas to see " \
                   "which Team will prevail!"
        else:
            return "Noot vs Doot is over! Team " + winningTeamName + " has won Christmas!"

    def autoActivate(self, channelName):
        # used to enable NvD automatically on Bot start if active in DB
        selectNVD = "SELECT * from NootVsDootMain " \
                    "INNER JOIN ChannelList cl USING(channelID) " \
                    "WHERE cl.channelName = ?"
        NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName, ))
        print(NVDList[0])
        if NVDList:
            print(NVDList[0][2])
            if NVDList[0][2] == "False":
                print("False")
                active = False
            else:
                print("True")
                active = True
            print(active)
            if active is True:
                print("Noot vs Doot is active in DB")
                self.enableNootVsDoot(channelName)
            else:
                print("Auto Activate: Noot vs Doot is not active for " + channelName)
        else:
            print("No Noot vs Doot entry for " + channelName)

    def enableNootVsDoot(self, channelName):
        # set Noot and Doot to active in object and database
        selectNVD = "SELECT * from NootVsDootMain " \
                    "INNER JOIN ChannelList cl USING(channelID) " \
                    "WHERE cl.channelName = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if activeDB:
            self.cacheChannel(channelName)
            if self.debug == 1:
                print(f"Read from DB: {activeDB[0]}")
            if activeDB[0][2] == 'True':
                # is active already so update from table (load if active already)
                # print(self.teamsDict)
                self.teamsDict[channelName]["noot"]["total"] = activeDB[0][3]
                self.teamsDict[channelName]["doot"]["total"] = activeDB[0][4]
                self.teamsDict[channelName]["third"]["total"] = activeDB[0][5]
                self.teamsDict[channelName]["third"]["name"] = activeDB[0][6]
                self.teamsDict[channelName]["third"]["value"] = activeDB[0][7]
                if self.debug == 1:
                    print("Noot vs Doot is still active, loading values!")
            else:
                # is not currently active so clear out values in the DB and activate
                if self.debug == 1:
                    print(f"attempting to reset NootVsDoot values: {self.channelCache[channelName]['id']}")
                updateNVD = "UPDATE NootVsDootMain " \
                            "SET active = 'True', nootTotal = 0, dootTotal = 0, " \
                            "thirdTotal = 0, thirdName = NULL, thirdBitAmount = NULL "\
                            "WHERE channelID = ?"
                self.execute_write_query(self.dbConnection, updateNVD, (self.channelCache[channelName]["id"],))
                if self.debug == 1:
                    print("Noot vs Doot is not active, resetting any values and enabling!")
        else:
            # is not in DB yet, add to DB
            self.cacheChannel(channelName)
            insertNVD = "INSERT INTO NootVsDootMain " \
                        "(channelID, active, nootTotal, dootTotal, thirdTotal, thirdName, thirdBitAmount) " \
                        "VALUES (?, 'True', 0, 0, 0, NULL, NULL)"
            self.execute_write_query(self.dbConnection, insertNVD, (self.channelCache[channelName]["id"],))
            print("Noot vs Doot is not present, creating entry in DB!")
        self.active = True
        print("Noot vs Doot is live!")

    def disableNootVsDoot(self, channelName):
        # set Noot and Doot to inactive in object and database
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelID = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (self.channelCache[channelName]["id"],))
        if activeDB:
            # print(activeDB[0])
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET active = 'False', nootTotal = 0, dootTotal = 0, " \
                        "thirdTotal = 0, thirdName = NULL, thirdBitAmount = NULL "\
                        "WHERE channelID = ?"
            self.execute_write_query(self.dbConnection, updateNVD, (self.channelCache[channelName]["id"],))
            updateNVDViewers = "UPDATE NootVsDootViewers " \
                               "SET currentTeam = NULL, nootAmount = 0, dootAmount = 0, " \
                               "thirdAmount = 0, captainPoints = 0 " \
                               "WHERE channelID = ?"
            self.execute_write_query(self.dbConnection, updateNVDViewers, (self.channelCache[channelName]["id"], ))
            self.teamsDict.pop(channelName)
            self.active = False
            print("The War for Christmas has come to a close.")
        else:
            print("No row found in DB for " + channelName)

    def enableExtraTeam(self, channelName, thirdTeamName, thirdTeamBit):
        # set thirdTeamName as active and set bit value as thirdTeamBit
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelID = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (self.channelCache[channelName]["id"],))
        if activeDB:
            print(activeDB[0])
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET thirdName = ?, thirdBitAmount = ? " \
                        "WHERE channelID = ?"
            self.execute_write_query(self.dbConnection, updateNVD,
                                     (thirdTeamName.lower(), thirdTeamBit, self.channelCache[channelName]["id"]))
            self.teamsDict[channelName]["third"]["name"] = thirdTeamName.lower()
            self.teamsDict[channelName]["third"]["value"] = thirdTeamBit
            return "Team " + thirdTeamName + " joins the battle! " \
                   "Cheer " + str(thirdTeamBit) + " bits or donate " + \
                   str(float(thirdTeamBit/10)) + " to join Team " + thirdTeamName + "!"
        else:
            return "No row found in DB for " + channelName

    def viewerStatsLookup(self, channelName, viewerName):
        # call to lookup viewer details from DB, returns list as it appears from DB
        selectNVDViewers = "SELECT * FROM NootVsDootViewers nv " \
                           "INNER JOIN ViewerList vl USING(viewerID) " \
                           "WHERE channelID = ? AND vl.viewerName = ?"
        viewerList = self.execute_read_query(self.dbConnection, selectNVDViewers,
                                             (self.channelCache[channelName]["id"], viewerName))
        return viewerList

    def adjustTeamCaptainPoints(self, teamName, viewerDict, value):
        # This function is used to change captain points for individual donations
        # it doesn't call the DB, so it doesn't need channelName
        viewerTeamDict = dict({"noot": viewerDict["noot"], "doot": viewerDict["doot"], "third": viewerDict["third"]})
        sortTeamDict = sorted(viewerTeamDict.items(), key=lambda x: x[1], reverse=True)
        currentTeam = viewerDict["team"]
        if currentTeam.lower() == teamName or currentTeam is None:
            currentTeam = teamName
            newCaptainPoints = viewerDict["captainPoints"] + value
        else:
            # find out if a team change is in order
            highestTeamName = sortTeamDict[0][0]
            if highestTeamName == teamName:
                # changing team
                currentTeam = teamName
                newCaptainPoints = viewerDict["captainPoints"] + value
            else:
                # penalize captain points for betrayal of team
                newCaptainPoints = viewerDict["captainPoints"] - 1
                if newCaptainPoints < 0:
                    newCaptainPoints = 0
        return newCaptainPoints, currentTeam

    def addDonation(self, channelName, teamName, viewerName, donation=0):
        # add donation to teamName, donation is broken down into noots/doots if present
        # if no donation value is present, counts as 1 noot/doot
        teamNameList = self.teamsDict[channelName].keys()
        teamNameLower = teamName.lower()
        actualTeamName = self.teamsDict[channelName][teamNameLower]["name"]
        if teamNameLower in teamNameList:
            if re.match(r"\d+\.\d+", str(donation)):
                # adjusting donation amount to bits
                donation *= 100

            if donation > 0:
                # time to figure out the value of noots/doots to be added based on the donation
                valueToBeAdded = int(donation / self.teamsDict[channelName][teamNameLower]["value"])
            else:
                # default adds one noot/doot/whatever
                valueToBeAdded = 1

            # time to add values to DB and totals list
            # add the donated value to the correct team
            self.teamsDict[channelName][teamNameLower]["total"] += valueToBeAdded
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET nootTotal = ?, dootTotal = ?, thirdTotal = ? " \
                        "WHERE channelID = ?"
            self.execute_write_query(self.dbConnection, updateNVD,
                                     (self.teamsDict[channelName]["noot"]["total"],
                                      self.teamsDict[channelName]["doot"]["total"],
                                      self.teamsDict[channelName]["third"]["total"],
                                      self.channelCache[channelName]["id"]))
            viewerList = self.viewerStatsLookup(channelName, viewerName)
            if viewerList:
                print(viewerList)
                viewerDict = dict(self.defaultViewerDict)
                viewerDict["id"] = viewerList[0][2]
                if viewerList[0][3]:
                    viewerDict["team"] = viewerList[0][3]
                else:
                    viewerDict["team"] = teamName
                viewerDict["noot"] = viewerList[0][4]
                viewerDict["doot"] = viewerList[0][5]
                viewerDict["third"] = viewerList[0][6]
                viewerDict["captainPoints"] = viewerList[0][7]
                viewerDict[teamNameLower] += valueToBeAdded  # adds the value to the listed team
                newCaptainPoints, currentTeam = \
                    self.adjustTeamCaptainPoints(teamNameLower, viewerDict, valueToBeAdded)
                updateNVDViewers = "UPDATE NootVsDootViewers " \
                                   "SET currentTeam = ?, nootAmount = ?, dootAmount = ?, " \
                                   "thirdAmount = ?, captainPoints = ? " \
                                   "WHERE channelID = ? AND viewerID = ?"
                self.execute_write_query(self.dbConnection, updateNVDViewers,
                                         (currentTeam, viewerDict["noot"], viewerDict["doot"], viewerDict["third"],
                                          newCaptainPoints, self.channelCache[channelName]["id"], viewerDict["id"]))
                return "Added " + str(valueToBeAdded) + " points to " \
                       "Team " + actualTeamName.capitalize() + " for " + viewerName
            else:
                viewerDict = dict(self.defaultViewerDict)
                selectViewer = "SELECT viewerID FROM ViewerList " \
                               "WHERE viewerName = ?"
                viewerList = self.execute_read_query(self.dbConnection, selectViewer, (viewerName,))
                viewerDict["id"] = viewerList[0][0]
                viewerDict["team"] = teamName
                viewerDict["noot"] = 0
                viewerDict["doot"] = 0
                viewerDict["third"] = 0
                viewerDict["captainPoints"] = valueToBeAdded
                viewerDict[teamNameLower] += valueToBeAdded  # adds the value to the listed team
                insertNVDViewers = "INSERT into NootVsDootViewers " \
                                   "(channelID, viewerID, currentTeam, " \
                                   "nootAmount, dootAmount, thirdAmount, captainPoints) " \
                                   "VALUES (?, ?, ?, ?, ?, ?, ?)"
                self.execute_write_query(self.dbConnection, insertNVDViewers,
                                         (self.channelCache[channelName]["id"], viewerDict["id"], viewerDict["team"],
                                          viewerDict["noot"], viewerDict["doot"], viewerDict["third"],
                                          viewerDict["captainPoints"]))
                return "Added " + str(valueToBeAdded) + " points to " \
                       "Team " + actualTeamName.capitalize() + " for " + viewerName
        else:
            return teamName + " is an invalid Team Name."

    def removeDonation(self, channelName, teamName, viewerName, donation=0):
        # remove a donation from teamName, donation is broken down into noots/doots if present
        # if no donation present, counts as 1 noot/doot
        teamNameList = self.teamsDict[channelName].keys()
        teamNameLower = teamName.lower()
        actualTeamName = self.teamsDict[channelName][teamNameLower]["name"]
        if teamNameLower in teamNameList:
            if re.match(r"\d+\.\d+", str(donation)):
                # adjusting donation amount to bits
                donation *= 100

            if donation > 0:
                # time to figure out the value of noots/doots to be added based on the donation
                valueToBeSubtracted = int(donation / self.teamsDict[channelName][teamNameLower]["value"])
            else:
                # default removes one noot/doot/whatever
                valueToBeSubtracted = 1

            # time to subtract values from DB and totals list
            self.teamsDict[channelName][teamNameLower]["total"] -= valueToBeSubtracted
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET nootTotal = ?, dootTotal = ?, thirdTotal = ? " \
                        "WHERE channelID = ?"
            self.execute_write_query(self.dbConnection, updateNVD,
                                     (self.teamsDict[channelName]["noot"]["total"],
                                      self.teamsDict[channelName]["doot"]["total"],
                                      self.teamsDict[channelName]["third"]["total"],
                                      self.channelCache[channelName]["id"]))
            viewerList = self.viewerStatsLookup(channelName, viewerName)
            if viewerList:
                print(viewerList)
                viewerDict = dict(self.defaultViewerDict)
                viewerDict["id"] = viewerList[0][2]
                viewerDict["team"] = viewerList[0][3]
                viewerDict["noot"] = viewerList[0][4]
                viewerDict["doot"] = viewerList[0][5]
                viewerDict["third"] = viewerList[0][6]
                viewerDict["captainPoints"] = viewerList[0][7]
                viewerDict[teamNameLower] -= valueToBeSubtracted  # adds the value to the listed team
                updateNVDViewers = "UPDATE NootVsDootViewers " \
                                   "SET nootAmount = ?, dootAmount = ?, thirdAmount = ? " \
                                   "WHERE channelID = ? AND viewerID = ?"
                self.execute_write_query(self.dbConnection, updateNVDViewers,
                                         (viewerDict["noot"], viewerDict["doot"], viewerDict["third"],
                                          self.channelCache[channelName]["id"], viewerDict["id"]))
                return "Removed " + str(valueToBeSubtracted) + " points from " \
                       "Team " + actualTeamName.capitalize() + " for " + viewerName
            else:
                return "Can't remove " + str(donation) + " donation from " + viewerName + "'s tracking, as they " \
                      "aren't in the DB. overall totals are adjusted. Please add the viewer manually."
        else:
            return teamName + " is an invalid Team Name."

    def forceTeamChange(self, channelName, viewerName, teamName):
        # change viewerName's team affiliation to teamName
        teamNameList = self.teamsDict[channelName].keys()
        teamNameLower = teamName.lower()
        actualTeamName = self.teamsDict[channelName][teamNameLower]["name"]
        if teamNameLower in teamNameList:
            NVDViewers = self.viewerStatsLookup(channelName, viewerName)
            if NVDViewers:
                viewerDict = dict(self.defaultViewerDict)
                viewerDict["id"] = NVDViewers[0][2]
                viewerDict["team"] = teamName
                updateNVDViewer = "UPDATE NootVsDootViewers " \
                                  "SET currentTeam = ? " \
                                  "WHERE channelID = ? AND viewerID = ?"
                self.execute_write_query(self.dbConnection, updateNVDViewer,
                                         (teamName, self.channelCache[channelName]["id"], viewerDict["id"]))
                return viewerName + " is now on team " + actualTeamName
            else:
                viewerDict = dict(self.defaultViewerDict)
                selectViewer = "SELECT viewerID FROM ViewerList " \
                               "WHERE viewerName = ?"
                viewerList = self.execute_read_query(self.dbConnection, selectViewer, (viewerName,))
                viewerDict["id"] = viewerList[0][0]
                viewerDict["team"] = teamName
                insertNVDViewer = "INSERT into NootVsDootViewers " \
                                  "(channelID, viewerID, currentTeam, nootAmount, " \
                                  "dootAmount, thirdAmount, captainPoints) " \
                                  "VALUES (?, ?, ?, 0, 0, 0, 0)"
                self.execute_write_query(self.dbConnection, insertNVDViewer,
                                         (self.channelCache[channelName]["id"], viewerDict["id"], teamName))
                return viewerName + " is now on team " + actualTeamName
        else:
            print(teamName + " is an invalid Team Name. But the command should have checked this as well...")

    def forceAddRemove(self, channelName, teamName, value):
        # adds noots/doots without assigning the points to a viewer
        teamNameList = self.teamsDict[channelName].keys()
        teamNameLower = teamName.lower()
        if teamNameLower in teamNameList:
            self.teamsDict[channelName][teamNameLower]["total"] += value
            if self.teamsDict[channelName][teamNameLower]["total"] < 0:
                self.teamsDict[channelName][teamNameLower]["total"] = 0
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET nootTotal = ?, dootTotal = ?, thirdTotal = ? " \
                        "WHERE channelID = ?"
            self.execute_write_query(self.dbConnection, updateNVD,
                                     (self.teamsDict[channelName]["noot"]["total"],
                                      self.teamsDict[channelName]["doot"]["total"],
                                      self.teamsDict[channelName]["third"]["total"],
                                      self.channelCache[channelName]["id"]))
        else:
            print(teamName + " is an invalid Team Name.")

    def forceCaptainPoints(self, channelName, viewerName, value):
        # used for manually adjusting Captain Points for viewerName
        NVDViewerList = self.viewerStatsLookup(channelName, viewerName)
        if NVDViewerList:
            viewerDict = dict(self.defaultViewerDict)
            viewerDict["id"] = NVDViewerList[0][2]
            viewerDict["captainPoints"] = NVDViewerList[0][7]
            newCaptainPoints = viewerDict["captainPoints"] + value
            if newCaptainPoints < 0:
                newCaptainPoints = 0
            updateNVDViewer = "UPDATE NootVsDootViewers " \
                              "SET captainPoints = ? " \
                              "WHERE channelID = ? AND viewerID = ?"
            self.execute_write_query(self.dbConnection, updateNVDViewer,
                                     (newCaptainPoints, self.channelCache[channelName]["id"], viewerDict["id"]))
            return "Adjusted " + viewerName + "'s captain points to " + str(newCaptainPoints)
        else:
            if value < 0:
                value = 0
            viewerDict = dict(self.defaultViewerDict)
            selectViewer = "SELECT viewerID FROM ViewerList " \
                           "WHERE viewerName = ?"
            viewerList = self.execute_read_query(self.dbConnection, selectViewer, (viewerName,))
            viewerDict["id"] = viewerList[0][0]
            insertNVDViewer = "INSERT into NootVsDootViewers " \
                              "(channelID, viewerID, nootAmount, dootAmount, thirdAmount, captainPoints) " \
                              "VALUES (?, ?, 0, 0, 0, ?)"
            self.execute_write_query(self.dbConnection, insertNVDViewer,
                                     (self.channelCache[channelName]["id"], viewerDict["id"], value))
            return "Set " + viewerName + "'s captain points to " + str(value)

    def create_connection(self, path):
        connection = None
        try:
            connection = sqlite3.connect(path)
            # print("Connection to SQLite DB successful")
        except Error as e:
            print(f"The error '{e}' occurred")
        return connection

    def execute_write_query(self, connection, query, args):
        cursor = connection.cursor()
        try:
            cursor.execute(query, args)
            connection.commit()
            # print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_read_query(self, connection, query, args):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, args)
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"The error '{e}' occurred")
