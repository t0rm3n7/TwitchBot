import random
import sqlite3
from sqlite3 import Error
import pickle


class Raffle:
    defaultRaffleDict = {
        "channel": "",
        "tickets": [],
        "prize": "",
        "active": False
    }
    raffleDict = {}
    print(raffleDict)

    def __init__(self):
        print("raffle init")

    def open_raffle(self, channelName, rafflePrize):
        print("Current RaffleDict:")
        print(self.raffleDict)
        if channelName in self.raffleDict.keys():
            self.close_raffle(channelName)
        print("Default:")
        print(self.defaultRaffleDict)
        newRaffleDict = self.defaultRaffleDict.copy()
        newRaffleDict["channel"] = channelName
        newRaffleDict["prize"] = rafflePrize
        newRaffleDict["tickets"] = []
        self.raffleDict.update({channelName: newRaffleDict.copy()})
        print("Freshly added Dict:")
        print(self.raffleDict)
        dbConnection = sqlite3.connect(".\\TwitchBot.sqlite")
        select_raffle = "SELECT * FROM Raffle " \
                        "INNER JOIN ChannelList cl USING(channelID) " \
                        "WHERE cl.channelName = ?"
        raffleBits = self.execute_read_query(dbConnection, select_raffle, (channelName, ))
        if not raffleBits:
            arguments = (channelName, rafflePrize, pickle.dumps([]).hex())
            insert_raffle = "INSERT into Raffle (channelID,prize,array) VALUES (?,?,?)"
            self.execute_write_query(dbConnection, insert_raffle, arguments)
            self.raffleDict[channelName]["active"] = True
        elif raffleBits:
            raffleID = raffleBits[0][0]
            arguments = (rafflePrize, pickle.dumps([]).hex(), raffleID)
            update_raffle = "UPDATE Raffle SET prize = ?, array = ? where raffleID = ?"
            self.execute_write_query(dbConnection, update_raffle, arguments)
            self.raffleDict[channelName]["active"] = True
        else:
            print("raffle shouldn't be active")

    def load_raffle(self, channelName):
        if channelName not in self.raffleDict.keys():
            dbConnection = sqlite3.connect(".\\TwitchBot.sqlite")
            select_raffle = "SELECT * FROM Raffle " \
                            "INNER JOIN ChannelList cl USING(channelID) " \
                            "WHERE cl.channelName = ?"
            raffleBits = self.execute_read_query(dbConnection, select_raffle, (channelName, ))
            if raffleBits:
                for raffleRow in raffleBits:
                    if raffleRow[2]:
                        newRaffleDict = dict(self.defaultRaffleDict)
                        newRaffleDict["channel"] = channelName
                        newRaffleDict["tickets"] = pickle.loads(bytes.fromhex(raffleRow[3]))
                        newRaffleDict["prize"] = raffleRow[2]
                        newRaffleDict["active"] = True
                        self.raffleDict.update({channelName: newRaffleDict})
                        return self.raffleDict[channelName]["active"]
                    else:
                        return None

    def add_tickets(self, channelName, username, numTickets):
        viewerName = str(username)
        for ticket in range(numTickets):
            self.raffleDict[channelName]["tickets"].append(viewerName)
        print(self.raffleDict[channelName]["tickets"])
        dbConnection = sqlite3.connect(".\\TwitchBot.sqlite")
        select_raffle = "SELECT * FROM Raffle " \
                        "INNER JOIN ChannelList cl USING(channelID) " \
                        "WHERE cl.channelName = ?"
        raffleBits = self.execute_read_query(dbConnection, select_raffle, (channelName,))
        if raffleBits:
            raffleID = raffleBits[0][0]
            update_raffle = "UPDATE Raffle SET array = ? where raffleID = ?"
            self.execute_write_query(dbConnection, update_raffle,
                                     (pickle.dumps(self.raffleDict[channelName]["tickets"]).hex(), raffleID))
            return self.list_tickets(channelName, viewerName)

    def draw_winner(self, channelName):
        if len(self.raffleDict[channelName]["tickets"]) < 1:
            self.raffleDict[channelName]["active"] = False
            self.raffleDict[channelName]["prize"] = ""
            return None
        else:
            winningTicket = random.randrange(0, len(self.raffleDict[channelName]["tickets"]))
            winner = self.raffleDict[channelName]["tickets"][winningTicket]
            self.raffleDict[channelName]["active"] = False
            self.raffleDict[channelName]["prize"] = ""
            self.remove_tickets(channelName, winner)
            return winner

    def is_active(self, channelName):
        if channelName in self.raffleDict.keys():
            return self.raffleDict[channelName]["active"]
        else:
            return False

    def what_prize(self, channelName):
        return self.raffleDict[channelName]["prize"]

    def in_list(self, channelName, username):
        if username in self.raffleDict[channelName]["tickets"]:
            return True
        else:
            return False

    def list_tickets(self, channelName, username):
        ticketTotal = 0
        for ticket in self.raffleDict[channelName]["tickets"]:
            if ticket == username:
                ticketTotal += 1
        return ticketTotal

    def update_prize(self, channelName, rafflePrize):
        self.raffleDict[channelName]["prize"] = rafflePrize
        dbConnection = sqlite3.connect(".\\TwitchBot.sqlite")
        select_raffle = "SELECT raffleID FROM Raffle " \
                        "INNER JOIN ChannelList cl USING(channelID) " \
                        "WHERE cl.channelName = ?"
        raffleBits = self.execute_read_query(dbConnection, select_raffle, (channelName,))
        if raffleBits:
            raffleID = raffleBits[0][0]
            update_raffle = "UPDATE Raffle SET prize = ? where raffleID = ?"
            self.execute_write_query(dbConnection, update_raffle, (rafflePrize, raffleID))

    def close_raffle(self, channelName):
        self.raffleDict.pop(channelName)
        dbConnection = sqlite3.connect(".\\TwitchBot.sqlite")
        select_raffle = "SELECT raffleID FROM Raffle " \
                        "INNER JOIN ChannelList cl USING(channelID) " \
                        "WHERE cl.channelName = ?"
        raffleBits = self.execute_read_query(dbConnection, select_raffle, (channelName,))
        if raffleBits:
            raffleID = raffleBits[0][0]
            update_raffle = "UPDATE Raffle SET prize = ?, array = ? where raffleID = ?"
            self.execute_write_query(dbConnection, update_raffle,
                                     ("", pickle.dumps([]).hex(), raffleID))

    def get_total_tickets(self, channelName):
        return len(self.raffleDict[channelName]["tickets"])

    def remove_tickets(self, channelName, username):
        for ticket in self.raffleDict[channelName]["tickets"]:
            if ticket == username:
                self.raffleDict[channelName]["tickets"].remove(username)

    def create_connection(self, path):
        connection = None
        try:
            connection = sqlite3.connect(path)
            # print("Connection to SQLite DB successful")
        except Error as e:
            print(f"The error '{e}' occurred")
        return connection

    def execute_write_query(self, connection, query, *args):
        cursor = connection.cursor()
        try:
            cursor.execute(query, *args)
            connection.commit()
            # print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_read_query(self, connection, query, *args):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, *args)
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"The error '{e}' occurred")
