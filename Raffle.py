import random
import sqlite3
from sqlite3 import Error
import ast
import pickle


class Raffle:
    ticketList = list([])
    print(ticketList)
    active = False
    prize = ""

    def __init__(self):
        print("init")

    def open_raffle(self, channelName, rafflePrize):
        self.prize = rafflePrize
        pointsConnection = sqlite3.connect(".\\points.sqlite")
        select_raffle = "SELECT * from Raffle where channel = '" + channelName + "'"
        raffleBits = self.execute_read_query(pointsConnection, select_raffle)
        if not raffleBits:
            arguments = (channelName, rafflePrize, pickle.dumps(self.ticketList).hex())
            insert_raffle = "INSERT into Raffle (channel,prize,array) VALUES (?,?,?)"
            self.execute_query(pointsConnection, insert_raffle, arguments)
            self.active = True
        elif raffleBits:
            arguments = (rafflePrize, pickle.dumps(self.ticketList).hex())
            update_raffle = "UPDATE Raffle SET prize = ?, array = ? where channel = '" + channelName + "'"
            self.execute_query(pointsConnection, update_raffle, arguments)
            self.active = True
        else:
            print("raffle shouldn't be active")

    def load_raffle(self, channelName):
        pointsConnection = sqlite3.connect(".\\points.sqlite")
        select_raffle = "SELECT * from Raffle where channel = '" + channelName + "'"
        raffleBits = self.execute_read_query(pointsConnection, select_raffle)
        if raffleBits:
            for raffleRow in raffleBits:
                if raffleRow[2]:
                    self.prize = raffleRow[2]
                    self.ticketList = pickle.loads(bytes.fromhex(raffleRow[3]))
                    self.active = True
                    return self.prize
                else:
                    return None

    def add_tickets(self, channelName, username, numTickets):
        viewerName = str(username)
        for ticket in range(numTickets):
            self.ticketList.append(viewerName)
        print(self.ticketList)
        pointsConnection = sqlite3.connect(".\\points.sqlite")
        update_raffle = "UPDATE Raffle SET array = ? where channel = '" + channelName + "'"
        self.execute_query(pointsConnection, update_raffle, (pickle.dumps(self.ticketList).hex(),))
        return self.list_tickets(viewerName)

    def draw_winner(self, channelName):
        if len(self.ticketList) < 1:
            return None
        else:
            winningTicket = random.randrange(0, len(self.ticketList))
            winner = self.ticketList[winningTicket]
            return winner

    def is_active(self):
        return self.active

    def what_prize(self):
        return self.prize

    def in_list(self, username):
        if username in self.ticketList:
            return True
        else:
            return False

    def list_tickets(self, username):
        ticketTotal = 0
        for ticket in self.ticketList:
            if ticket == username:
                ticketTotal += 1
        return ticketTotal

    def update_prize(self, channelName, rafflePrize):
        self.prize = rafflePrize
        pointsConnection = sqlite3.connect(".\\points.sqlite")
        update_raffle = "UPDATE Raffle SET prize = ? where channel = '" + channelName + "'"
        self.execute_query(pointsConnection, update_raffle, (rafflePrize,))

    def close_raffle(self, channelName):
        self.active = False
        self.prize = ""
        self.ticketList = list([])
        pointsConnection = sqlite3.connect(".\\points.sqlite")
        update_raffle = "UPDATE Raffle SET prize = ?, array = ? where channel = '" + channelName + "'"
        self.execute_query(pointsConnection, update_raffle, (self.prize, pickle.dumps(self.ticketList).hex()))

    def get_total_tickets(self):
        return len(self.ticketList)

    def create_connection(self, path):
        connection = None
        try:
            connection = sqlite3.connect(path)
            # print("Connection to SQLite DB successful")
        except Error as e:
            print(f"The error '{e}' occurred")
        return connection

    def execute_query(self, connection, query, args):
        cursor = connection.cursor()
        try:
            cursor.execute(query, args)
            connection.commit()
            # print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_read_query(self, connection, query):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query)
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"The error '{e}' occurred")
