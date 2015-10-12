#!/usr/bin/env python
#
# tournament.py -- implementation of a Swiss-system tournament
#

import psycopg2
from random import choice, shuffle, randint
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def initConnect():
    """
    Connect to the default PostgreSQL database 'postgres' and create database
    'tournament'.
    """
    db=psycopg2.connect("dbname=postgres")
    db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    c = db.cursor()
    c.execute('DROP database IF EXISTS tournament;')
    c.execute('CREATE database tournament;')
    db.close()

def connect():
    """Connect to the PostgreSQL database.  Returns a database connection."""
    return psycopg2.connect("dbname=tournament")

def initTournament():
    """Connect to the PostgreSQL database 'tournament' and initialize the
       database with necessary tables and sequence
       """
    db = connect()
    c = db.cursor()
    query = '''
    DROP sequence IF EXISTS number;
    CREATE TABLE players(player_id SERIAL PRIMARY KEY, name TEXT);
    CREATE TABLE matches(match_num INTEGER,
                         player_id INTEGER REFERENCES players,
                         play_against INTEGER REFERENCES players,
                         wins INTEGER,
                         points INTEGER);
    CREATE TABLE bye(player_id SERIAL PRIMARY KEY,
                     bye BOOLEAN default False);
    CREATE SEQUENCE number;
    '''
    c.execute(query)
    db.commit()
    db.close()

def deleteMatches():
    """Remove all the match records from the database."""
    db = connect()
    c = db.cursor()
    query = '''
    DELETE FROM matches;
    '''
    c.execute(query)
    db.commit()
    db.close()

def deletePlayers():
    """Remove all the player records from the database."""
    db = connect()
    c = db.cursor()
    query = '''
    DELETE FROM players;
    '''
    c.execute(query)
    db.commit()
    db.close()

def deleteBye():
    """Remove all the player BYE records from the database."""
    db = connect()
    c = db.cursor()
    query = '''
    DELETE FROM bye;
    '''
    c.execute(query)
    db.commit()
    db.close()

def countPlayers():
    """Returns the number of players currently registered."""
    db = connect()
    c = db.cursor()
    query = '''
    SELECT count(*) AS total FROM players;
    '''
    c.execute(query)
    count = c.fetchone()
    db.close()
    return count[0]

def registerPlayer(name):
    """Adds a player to the tournament database.

    The database assigns a unique serial id number for the player in two
    different database: players and bye. Players database has the full name
    associated to that id number, while bye database has the bye status
    associated to that id number. (This should be handled by your SQL database
    schema, not in your Python code.)

    Args:
      name: the player's full name (need not be unique).
    """
    db = connect()
    c = db.cursor()
    query = '''
    INSERT INTO players (player_id, name) VALUES (DEFAULT, %s);
    INSERT INTO bye (player_id, bye) VALUES (DEFAULT, DEFAULT);
    '''
    c.execute(query, (name,))
    db.commit()
    db.close()

def playerStandings():
    """Returns a list of the players and their win records, sorted by wins and
    omw.

    The first entry in the list should be the player in first place, or a player
    tied for first place if there is currently a tie.

    Returns:
      A list of tuples, each of which contains
      (id, name, matches, wins, omw, points):
        id: the player's unique id (assigned by the database)
        name: the player's full name (as registered)
        matches: the number of matches the player has played
        wins: the number of matches the player has won
        omw: the player's OMW (Opponent Match Wins), the total number of wins by
             players they have played against
       points: the player's current points earned from win/lose/draw
    """
    db = connect()
    c = db.cursor()
    query = '''
    CREATE VIEW omw AS
      SELECT x.player_id,
             SUM(y.omw) as omw
      FROM
      (
        SELECT DISTINCT player_id, play_against
        FROM matches
      ) as x
      RIGHT JOIN
      (
        SELECT players.player_id,
               COALESCE(SUM(matches.wins),0) as omw
        FROM players LEFT JOIN matches
        ON players.player_id = matches.player_id
        GROUP BY players.player_id
      ) as y
      ON x.play_against = y.player_id
      GROUP BY 1
      ORDER BY 2 DESC;

    SELECT players.player_id,
           players.name,
           COUNT(DISTINCT matches.match_num) as matches,
           COALESCE(SUM(matches.wins),0) as wins,
           COALESCE(omw.omw,0),
           COALESCE(SUM(matches.points),0) as points,
           bye.bye as bye
    FROM players LEFT JOIN matches ON players.player_id = matches.player_id
    LEFT JOIN omw ON players.player_id = omw.player_id
    JOIN bye ON players.player_id = bye.player_id
    GROUP BY players.player_id, omw.omw, bye
    ORDER BY 4 DESC, 5 DESC;
    '''
    c.execute(query)
    standing = c.fetchall()
    db.close()
    return standing

def reportMatch(player1, player2):
    """Records the outcome of a single match between two players.

    Args:
      player1:  the id number of player 1
      player2:  the id number of player 2
    """
    db = connect()
    c = db.cursor()
    query='''
    SELECT NEXTVAL('number');
    '''
    c.execute(query)
    n = c.fetchone()[0]
    (player1_point, player1_win, player2_point, player2_win) = coinToss()
    query = '''
    INSERT INTO matches VALUES (%s, %s, %s, %s, %s);
    INSERT INTO matches VALUES (%s, %s, %s, %s, %s);
    '''
    c.execute(query, (n, player1, player2, player1_win, player1_point,
                      n, player2, player1, player2_win, player2_point))
    db.commit()
    db.close()

def swissPairings(printing=False):
    """Returns a list of pairs of players for the next round of a match.

    Assuming that there are an even number of players registered, each player
    appears exactly once in the pairings.  Each player is paired with another
    player with an equal or nearly-equal win record, that is, a player adjacent
    to him or her in the standings.

    Args:
      printing: For demo mode. If True, the function will call printStandings()
      and print out a table of current player standings before the next round

    Returns:
      A list of tuples, each of which contains (id1, name1, id2, name2)
        id1: the first player's unique id
        name1: the first player's name
        id2: the second player's unique id
        name2: the second player's name
    """
    standings=playerStandings()
    if printing==True:
        printStandings(standings)
    ranking=0
    matches=[]
    bye=[]
    if countPlayers()%2==0:
        pass
    else:
        while True:
            n=randint(0,countPlayers()-1)
            if standings[n][-1]:
                pass
            else:
                bye=standings.pop(n)
                updateBye(bye)
                break
    for round in range(0,int(countPlayers()/2.)):
        matches.append((standings[ranking][0],
                        standings[ranking][1],
                        standings[ranking+1][0],
                        standings[ranking+1][1]))
        ranking+=2
    return matches

def updateBye(bye):
    """
    Update bye status of a selected player to TRUE in table 'bye'.
    Also create new row in table 'matches' with player's win, and point.
    A bye game is equal to 1 win and 3 points. A bye game is not assigned with
    any match_num (in order for playerStandings() to ignore BYE game when
    counting total matches for each player)

    Arg:
        bye: a poped list from swissPairings() with current standing of the
             selected player - (id, name, matches, wins, omw, points)
    """
    db = connect()
    c = db.cursor()
    query = '''
    INSERT INTO matches (player_id, wins, points)
         VALUES (%s, 1, 3);
    UPDATE bye SET bye = TRUE WHERE player_id = %s;
    '''
    c.execute(query, (bye[0], bye[0]))
    db.commit()
    db.close()

def coinToss():
    """Returns a tuple of player 1 and player 2's points received and number of
       win received

    Used in demo mode to generate random events of player winning, losing, or
    drawing. For each call of coinToss(), players receive 3 points, 1 points,
    or 0 points for winning, drawing, or losing respectively. Players will also
    receive 1 or 0 win for each call of coinToss().

    Returns:
    A tuple contains (player1_point, player1_win, player2_point, player2_win)
    player1_point: point received by player 1 (either 0, 1, or 3)
    player1_win: number of win received by player 1 (either 1 or 0)
    player2_point: point received by player 2 (either 0, 1, or 3)
    player2_win: number of win received by player 2 (either 1 or 0)
    """
    player1_point=choice([0,1,3])
    if player1_point == 1:
        (player1_win, player2_point, player2_win) = (0, 1, 0)
    elif player1_point == 0:
        (player1_win, player2_point, player2_win) = (0, 3, 1)
    else:
        (player1_win, player2_point, player2_win) = (1, 0, 0)
    return (player1_point, player1_win, player2_point, player2_win)

def printStandings(standings):
    """
    Print the current Player Standings in a left-alinging format

    Args:
      standings: output from playerStandings()
    """

    column_width=20
    headers=('player ID', 'Name','Matches', 'Wins','OMW','Points','BYE')
    for header in headers:
        print header.ljust(column_width),
    print
    for x in standings:
        for data in x:
            print str(data).ljust(column_width),
        print
    print
