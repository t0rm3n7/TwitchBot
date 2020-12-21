import sqlite3
from sqlite3 import Error
import re


class NootVsDoot:
    # teams should follow format [noot, doot, etc]
    teams = ["noot", "doot", None]
    teamTotals = [0, 0, 0]
    teamValues = [1225, 1224, 1226]
    teamCaptains = ["", "", ""]
    active = False
    dbConnection = ""

    def __init__(self):
        self.dbConnection = self.create_connection(".\\points.sqlite")
        print("noot init")

    def isActive(self, channelName):
        # returns Active column from DB for channelName
        NVDList = self.currentStats(channelName)
        return NVDList[0][2]

    def isThird(self, channelName):
        # returns Third team name and bit total for channelName
        NVDList = self.currentStats(channelName)
        return NVDList[0][6], NVDList[0][7]

    def currentStats(self, channelName):
        # looks up Noot vs Doot info for channelName
        selectNVD = "SELECT * from NootVsDootMain " \
                    "WHERE channelName = ?"
        NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName, ))
        return NVDList

    def determineWinner(self, channelName):
        NVDList = self.currentStats(channelName)
        pointsList = [NVDList[0][3], NVDList[0][4], NVDList[0][5]]
        sortList = list(pointsList)
        sortList.sort(reverse=True)
        winningValue = sortList[0]
        winningIndex = pointsList.index(winningValue)
        winningTeam = self.teams[winningIndex]
        return winningTeam

    def autoActivate(self, channelName):
        # used to enable NvD automatically on Bot start if active in DB
        selectNVD = "SELECT * from NootVsDootMain " \
                    "WHERE channelName = ?"
        NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName, ))
        if NVDList:
            active = NVDList[0][2]
            if active:
                self.enableNootVsDoot(channelName)
            else:
                print("Noot vs Doot is not active")
        else:
            print("No Noot vs Doot entry for " + channelName)

    def enableNootVsDoot(self, channelName):
        # set Noot and Doot to active in object and database
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelName = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if activeDB:
            print(activeDB[0])
            if activeDB[0][2] == 'True':
                # is active already so update from table (load if active already)
                self.teamTotals = [activeDB[0][3], activeDB[0][4], activeDB[0][5]]
                self.teams[2] = activeDB[0][6]
                self.teamValues[2] = activeDB[0][7]
                print("Noot vs Doot is still active, loading values!")
            else:
                # is not currently active so clear out values in the DB and activate
                updateNVD = "UPDATE NootVsDootMain " \
                            "SET active = 'True', nootTotal = 0, dootTotal = 0, " \
                            "thirdTotal = 0, thirdName = NULL, thirdBitAmount = NULL "\
                            "WHERE channelName = ?"
                self.execute_write_query(self.dbConnection, updateNVD, (channelName,))
                print("Noot vs Doot is not active, resetting any values and enabling!")
        else:
            # is not in DB yet, add to DB
            insertNVD = "INSERT INTO NootVsDootMain " \
                        "(channelName, active, nootTotal, dootTotal, thirdTotal, thirdName, thirdBitAmount) " \
                        "VALUES (?, 'True', 0, 0, 0, NULL, NULL)"
            self.execute_write_query(self.dbConnection, insertNVD, (channelName,))
            print("Noot vs Doot is not present, creating entry in DB!")
        self.active = True
        print("Noot vs Doot is live!")

    def disableNootVsDoot(self, channelName):
        # set Noot and Doot to inactive in object and database
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelName = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if activeDB:
            print(activeDB[0])
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET active = 'False', nootTotal = 0, dootTotal = 0, " \
                        "thirdTotal = 0, thirdName = NULL, thirdBitAmount = NULL "\
                        "WHERE channelName = ?"
            self.execute_write_query(self.dbConnection, updateNVD, (channelName,))
            updateNVDViewers = "UPDATE NootVsDootViewers " \
                               "SET currentTeam = NULL, nootAmount = 0, dootAmount = 0, " \
                               "thirdAmount = 0, captainPoints = 0 " \
                               "WHERE channelName = ?"
            self.execute_write_query(self.dbConnection, updateNVDViewers, (channelName, ))
            self.teams = ["Noot", "Doot", None]
            self.teamTotals = [0, 0, 0]
            self.teamCaptains = ["", "", ""]
            self.active = False
            print("The War for Christmas has come to a close.")
        else:
            print("No row found in DB for " + channelName)

    def enableExtraTeam(self, channelName, thirdTeamName, thirdTeamBit):
        # set thirdTeamName as active and set bit value as thirdTeamBit
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelName = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if activeDB:
            print(activeDB[0])
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET thirdName = ?, thirdBitAmount = ? " \
                        "WHERE channelName = ?"
            self.execute_write_query(self.dbConnection, updateNVD, (thirdTeamName.lower(), thirdTeamBit, channelName))
            self.teams[2] = thirdTeamName.lower()
            self.teamValues[2] = thirdTeamBit
            return "Team " + self.teams[2] + " joins the battle! " \
                   "Cheer " + str(self.teamValues[2]) + " bits or donate " + \
                   str(float(self.teamValues[2]/10)) + " to join Team " + self.teams[2] + "!"
        else:
            return "No row found in DB for " + channelName

    def viewerStatsLookup(self, channelName, viewerName):
        # call to lookup viewer details from DB, returns list as it appears from DB
        selectNVDViewers = "SELECT * from NootVsDootViewers " \
                           "WHERE channelName = ? AND viewerName = ?"
        viewerList = self.execute_read_query(self.dbConnection, selectNVDViewers, (channelName, viewerName))
        return viewerList

    def adjustTeamCaptainPoints(self, teamName, currentTeam, teamValues, value, currentCaptainPoints):
        # This function is used to change captain points for individual donations
        # it doesn't call the DB, so it doesn't need channelName
        sortValues = list(teamValues)
        sortValues.sort(reverse=True)
        if currentTeam.lower() == teamName or currentTeam is None:
            currentTeam = teamName
            newCaptainPoints = currentCaptainPoints + value
        else:
            # find out if a team change is in order
            bigValue = sortValues[0]
            teamIndex = self.teams.index(teamName.lower())
            bigIndex = teamValues.index(bigValue)
            if bigIndex == teamIndex:
                # changing team
                currentTeam = teamName
                newCaptainPoints = currentCaptainPoints + value
            else:
                # penalize captain points for betrayal of team
                newCaptainPoints = currentCaptainPoints - 1
                if newCaptainPoints < 0:
                    newCaptainPoints = 0
        return newCaptainPoints, currentTeam

    def addDonation(self, channelName, teamName, viewerName, donation=0):
        # add donation to teamName, donation is broken down into noots/doots if present
        # if no donation value is present, counts as 1 noot/doot
        if teamName.lower() in self.teams:
            teamIndex = self.teams.index(teamName.lower())

            if re.match(r"\d+\.\d+", str(donation)):
                # adjusting donation amount to bits
                donation *= 100

            if donation > 0:
                # time to figure out the value of noots/doots to be added based on the donation
                valueToBeAdded = int(donation / self.teamValues[teamIndex])
            else:
                # default adds one noot/doot/whatever
                valueToBeAdded = 1

            # time to add values to DB and totals list
            selectNVD = "SELECT * from NootVsDootMain " \
                        "WHERE channelName = ?"
            NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
            if NVDList:
                print(NVDList)
                currentValues = [NVDList[0][3], NVDList[0][4], NVDList[0][5]]
                newValues = list(currentValues)
                # add the donated value to the correct team
                newValues[teamIndex] += valueToBeAdded
                updateNVD = "UPDATE NootVsDootMain " \
                            "SET nootTotal = ?, dootTotal = ?, thirdTotal = ? " \
                            "WHERE channelName = ?"
                self.execute_write_query(self.dbConnection, updateNVD,
                                         (newValues[0], newValues[1], newValues[2], channelName))
                viewerList = self.viewerStatsLookup(channelName, viewerName)
                if viewerList:
                    print(viewerList)
                    currentTeam = viewerList[0][3]
                    currentValues = [viewerList[0][4], viewerList[0][5], viewerList[0][6]]
                    newValues = list(currentValues)
                    newValues[teamIndex] += valueToBeAdded  # adds the value to the listed team
                    currentCaptainPoints = viewerList[0][7]
                    newCaptainPoints, currentTeam = \
                        self.adjustTeamCaptainPoints(teamName, currentTeam, newValues,
                                                     valueToBeAdded, currentCaptainPoints)
                    updateNVDViewers = "UPDATE NootVsDootViewers " \
                                       "SET currentTeam = ?, nootAmount = ?, dootAmount = ?, " \
                                       "thirdAmount = ?, captainPoints = ? " \
                                       "WHERE channelName = ? AND viewerName = ?"
                    self.execute_write_query(self.dbConnection, updateNVDViewers,
                                             (currentTeam, newValues[0], newValues[1], newValues[2],
                                              newCaptainPoints, channelName, viewerName))
                    return "Added " + str(valueToBeAdded) + " points to " \
                           "Team " + teamName.capitalize() + " for " + viewerName
                else:
                    currentTeam = teamName
                    currentValues = [0, 0, 0]  # set team values to 0 for new row
                    newValues = list(currentValues)
                    newValues[teamIndex] += valueToBeAdded  # adds the value to the listed team
                    newCaptainPoints = valueToBeAdded
                    insertNVDViewers = "INSERT into NootVsDootViewers " \
                                       "(channelName, viewerName, currentTeam, " \
                                       "nootAmount, dootAmount, thirdAmount, captainPoints) " \
                                       "VALUES (?, ?, ?, ?, ?, ?, ?)"
                    self.execute_write_query(self.dbConnection, insertNVDViewers,
                                             (channelName, viewerName, currentTeam,
                                              newValues[0], newValues[1], newValues[2], newCaptainPoints))
                    return "Added " + str(valueToBeAdded) + " points to " \
                           "Team " + teamName.capitalize() + " for " + viewerName
            else:
                return "Couldn't find NootVsDoot entry for " + channelName
        else:
            return teamName + " is an invalid Team Name."

    def removeDonation(self, channelName, teamName, viewerName, donation=0):
        # remove a donation from teamName, donation is broken down into noots/doots if present
        # if no donation present, counts as 1 noot/doot
        if teamName.lower() in self.teams:
            teamIndex = self.teams.index(teamName.lower())

            if re.match(r"\d+\.\d+", str(donation)):
                # adjusting donation amount to bits
                donation *= 100

            if donation > 0:
                # time to figure out the value of noots/doots to be added based on the donation
                valueToBeAdded = int(donation / self.teamValues[teamIndex])
            else:
                # default removes one noot/doot/whatever
                valueToBeAdded = 1

            # time to add values to DB and totals list
            selectNVD = "SELECT * from NootVsDootMain " \
                        "WHERE channelName = ?"
            NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
            if NVDList:
                print(NVDList)
                currentValues = [NVDList[0][3], NVDList[0][4], NVDList[0][5]]
                newValues = list(currentValues)
                # add the donated value to the correct team
                newValues[teamIndex] -= valueToBeAdded
                updateNVD = "UPDATE NootVsDootMain " \
                            "SET nootTotal = ?, dootTotal = ?, thirdTotal = ? " \
                            "WHERE channelName = ?"
                self.execute_write_query(self.dbConnection, updateNVD,
                                         (newValues[0], newValues[1], newValues[2], channelName))
                viewerList = self.viewerStatsLookup(channelName, viewerName)
                if viewerList:
                    print(viewerList)
                    currentTeam = viewerList[0][3]
                    currentValues = [viewerList[0][4], viewerList[0][5], viewerList[0][6]]
                    newValues = list(currentValues)
                    newValues[teamIndex] -= valueToBeAdded  # removes the value to the listed team
                    updateNVDViewers = "UPDATE NootVsDootViewers " \
                                       "SET currentTeam = ?, nootAmount = ?, dootAmount = ?, " \
                                       "thirdAmount = ? " \
                                       "WHERE channelName = ? AND viewerName = ?"
                    self.execute_write_query(self.dbConnection, updateNVDViewers,
                                             (currentTeam, newValues[0], newValues[1], newValues[2],
                                              channelName, viewerName))
                    return "Removed " + str(valueToBeAdded) + " points from " \
                           "Team " + teamName.capitalize() + " for " + viewerName
                else:
                    return "Can't remove " + str(donation) + " donation from " + viewerName + "'s tracking, as they " \
                          "aren't in the DB. overall totals are adjusted. Please add the viewer manually."
            else:
                return "Couldn't find NootVsDoot entry for " + channelName
        else:
            return teamName + " is an invalid Team Name."

    def forceTeamChange(self, channelName, viewerName, teamName):
        # change viewerName's team affiliation to teamName
        if teamName.lower() in self.teams:
            NVDViewers = self.viewerStatsLookup(channelName, viewerName)
            if NVDViewers:
                updateNVDViewer = "UPDATE NootVsDootViewers " \
                                  "SET currentTeam = ? " \
                                  "WHERE channelName = ? AND viewerName = ?"
                self.execute_write_query(self.dbConnection, updateNVDViewer, (teamName, channelName, viewerName))
                return viewerName + " is now on team " + teamName
            else:
                insertNVDViewer = "INSERT into NootVsDootViewers " \
                                  "(channelName, viewerName, currentTeam, nootAmount, " \
                                  "dootAmount, thirdAmount, captainPoints) " \
                                  "VALUES (?, ?, ?, 0, 0, 0, 0)"
                self.execute_write_query(self.dbConnection, insertNVDViewer, (channelName, viewerName, teamName))
                return viewerName + " is now on team " + teamName
        else:
            print(teamName + " is an invalid Team Name. But the command should have checked this as well...")

    def forceAddRemove(self, channelName, teamName, value):
        # adds noots/doots without assigning the points to a viewer
        if teamName.lower() in self.teams:
            teamIndex = self.teams.index(teamName)
            selectNVD = "SELECT * from NootVsDootMain " \
                        "WHERE channelName = ?"
            NVDList = self.execute_read_query(self.dbConnection, selectNVD, (channelName, ))
            if NVDList:
                totalsList = [NVDList[0][3], NVDList[0][4], NVDList[0][5]]
                totalsList[teamIndex] += value
                if totalsList[teamIndex] < 0:
                    totalsList[teamIndex] = 0
                updateNVD = "UPDATE NootVsDootMain " \
                            "SET nootTotal = ?, dootTotal = ?, thirdTotal = ? " \
                            "WHERE channelName = ?"
                self.execute_write_query(self.dbConnection, updateNVD,
                                         (totalsList[0], totalsList[1], totalsList[2], channelName))
            else:
                print("No NootVsDoot row found for " + channelName + "'s channel.")
        else:
            print(teamName + " is an invalid Team Name.")

    def forceCaptainPoints(self, channelName, viewerName, value):
        # used for manually adjusting Captain Points for viewerName
        NVDViewerList = self.viewerStatsLookup(channelName, viewerName)
        if NVDViewerList:
            currentCaptainPoints = NVDViewerList[0][7]
            newCaptainPoints = currentCaptainPoints + value
            if newCaptainPoints < 0:
                newCaptainPoints = 0
            updateNVDViewer = "UPDATE NootVsDootViewers " \
                              "SET captainPoints = ? " \
                              "WHERE channelName = ? AND viewerName = ?"
            self.execute_write_query(self.dbConnection, updateNVDViewer, (newCaptainPoints, channelName, viewerName))
            return "Adjusted " + viewerName + "'s captain points to " + str(newCaptainPoints)
        else:
            if value < 0:
                value = 0
            insertNVDViewer = "INSERT into NootVsDootViewers " \
                              "(channelName, viewerName, nootAmount, dootAmount, thirdAmount, captainPoints) " \
                              "VALUES (?, ?, 0, 0, 0, ?)"
            self.execute_write_query(self.dbConnection, insertNVDViewer, (channelName, viewerName, value))
            return "Adjusted " + viewerName + "'s captain points to " + str(value)

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
