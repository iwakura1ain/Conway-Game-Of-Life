#!/usr/bin/python3
"""
John Conway's Game Of Life implemented in python by iwakura1ain. 
"""
__author__ = "https://github.com/iwakura1ain"
__version__ = "WIP"

from os import cpu_count
from itertools import repeat
from copy import copy
from random import randrange
from time import sleep

from multiprocessing import Pool, Event
from multiprocessing.managers import SharedMemoryManager
from threading import Thread

import curses
from curses import wrapper

import logging as l

# logging configuration 
l.basicConfig(level=l.DEBUG, filename="log.txt", filemode="a", format='%(message)s')


class GAME:
    """
    Global class inherited across all classes.
    Access to shared memory, events, and max lengths through singular instance of inherited class variables.

    NOTE: Because the shared memory identifier and events are initalized as a class variable here, inherited
    classes will share the same instance if made in the same module. But if imported and inherited elsewhere,
    the instances of those variables will be different, thus leading to errors.

    A classmethod that initializes these variables after instance creation might be better...
    """

    # dimentions of arena
    MAX_Y = 300  # Y axis length of arena
    MAX_X = 300  # X axis length of arena
    MAX_INDEX = MAX_X * MAX_Y  # index length of shared memory

    # shared memory manager process
    SHM_MANAGER = SharedMemoryManager()
    SHM_MANAGER.start()

    # singular shared memory identifier
    ARENA_SHM = SHM_MANAGER.SharedMemory(size=MAX_INDEX)
    ARENA = ARENA_SHM.buf

    # event for calculation start
    CALC_EVENT = Event()
    CALC_EVENT.set()

    # event for display read start
    DISPLAY_EVENT = Event()
    DISPLAY_EVENT.clear()

    def GetXaxis(self, x: int, current: int) -> int:
        """ Return the Xaxis offset from current index in shared memory. """

        if(GAME.MAX_X * int(current/GAME.MAX_X) <= current + x < GAME.MAX_X * int(current/GAME.MAX_X + 1)):
            return current + x

        else:
            raise IndexError

    def GetYaxis(self, y: int, current: int) -> int:
        """ Return the Yaxis offset from current index in shared memory. """

        if(0 <= current + y*GAME.MAX_X < GAME.MAX_INDEX):
            return current + y*GAME.MAX_X

        else:
            raise IndexError

    def GetOffset(self, x: int, y: int, current: int) -> int:
        """
        Return the X and Y axis offset from the current index in shared memory.
        If offset index is out of bounds, return None.
        """

        try:
            current = self.GetXaxis(x, current)
            current = self.GetYaxis(y, current)
            return current

        except IndexError:
            return None

    def GetOppositeCheck(self, check: int) -> int:
        """
        After each generation, the living bit alternates between bit index 0 and 1.
        Returns the next generation's bit index based on current bit index.
        """

        if(check == 0):
            return 1
        else:
            return 0

    def IsAlive(self, index: int, check: int) -> int:
        """
        Based on the check index and the index in shared memory,
        returns 1 if alive | returns 0 if dead or index is None.
        """

        if(index is None):
            return 0
        else:
            return int((copy(GAME.ARENA[index]) >> check) & 1)

        
class Overlord(GAME):
    """
    Process pool controller that manages jobs sent to children as well as signal events between the display thread.
    """

    def __init__(self, child_num: int):
        self.check = 0

        self.child_num = child_num
        self.child_pool = Pool(processes=self.child_num)  # child process pool

    def SwapCheck(self) -> int:
        """ Swaps the check index after every generation, returns the previous check index. """

        temp = self.check
        self.check = self.GetOppositeCheck(self.check)
        return temp

    def SeedRand(self) -> None:
        """ Randomly seeds the arena. """

        l.debug("waiting for calc event")
        self.CALC_EVENT.wait()
        l.debug("calc event received, seeding random")

        for i in [randrange(0, GAME.MAX_INDEX) for j in range(GAME.MAX_INDEX)]:
            temp = copy(GAME.ARENA[i])
            GAME.ARENA[i] = temp | (1 << self.check)

        self.CALC_EVENT.clear()
        self.DISPLAY_EVENT.set()
        l.debug("seed rand finished, display event set")

    def RunChildren(self) -> None:
        """
        Calculates the next generation using the process pool,
        returns the check index that was used in calculation.
        """

        l.debug("waiting for calc event")
        self.CALC_EVENT.wait()
        l.debug("calc event received, running children")

        #calls RunChild( [[index, check] * chunksize] )
        result = self.child_pool.starmap(Child.RunChild,
                                         zip(range(GAME.MAX_INDEX), repeat(self.check)),
                                         chunksize=30)

        # swaps check index after every generation
        prev_check = self.SwapCheck()

        self.CALC_EVENT.clear()
        self.DISPLAY_EVENT.set()
        l.debug("run children finished, display event set")

        return prev_check

    def SeedChildren(self, x: int = 0, y: int = 0) -> None:
        """ Seeds the arena at point [x, y] with contents of folder using the process pool. """

        l.debug("waiting for calc event")
        self.CALC_EVENT.wait()
        l.debug("calc event received, seeding children")

        seed_index = []
        with open("test.seed", "r") as fd:  # TODO: implement seed file selection
            lines = fd.readlines()
            for row, line in enumerate(lines):
                for col, char in enumerate(line):
                    if(char == "O"):
                        seed_index.append(self.GetOffset(x+col, y+row, 0))

        #call SeedChild( [[index, check] * chunksize] )
        result = self.child_pool.starmap(Child.SeedChild,
                                         zip(filter(lambda i: i is not None, seed_index), repeat(self.check)))

        self.CALC_EVENT.clear()
        self.DISPLAY_EVENT.set()
        l.debug("seed children finished, display event set")

    def JoinChildren(self) -> None:
        """ TODO: Implement clean exit... """

        self.CALC_EVENT.wait()

        try:
            GAME.shm_manager.shutdown()
            GAME.child_pool.close()
            GAME.child_pool.join()

        except:
            pass

        self.CALC_EVENT.clear()
        self.DISPLAY_EVENT.set()

        
class Child(GAME):
    """ Class used in child process for generation calculation. """

    @staticmethod
    def SeedChild(index: int, check: int) -> None:
        """ Process entry point for Overlord.SeedRand(). """

        current = Child()
        current.SetSeed(index, check)

    @staticmethod
    def RunChild(index: int, check: int) -> None:
        """ Process entry point for Overlord.RunChildren(). """

        current = Child()
        current.CalcGeneration(index, check)

    def __init__(self):
        self.index = None  # Current index being calculated
        self.check = None  # Bit index being read
        self.dest_check = None  # Bit index being written

    def Spawn(self) -> None:
        """ Set current cell bit to 1. """

        try:
            temp = copy(GAME.ARENA[self.index])
            GAME.ARENA[self.index] = temp | (1 << self.dest_check)
            return True

        except IndexError:
            pass

    def Kill(self) -> None:
        """ Set current cell bit to 0. """

        try:
            temp = copy(GAME.ARENA[self.index])
            GAME.ARENA[self.index] = temp & ~(1 << self.dest_check)
            return True

        except IndexError:
            pass

    def GetArea(self) -> None:
        """
        Returns the state of current index, number of living neighbours.

        N N N
        N C N
        N N N

        """

        current = 0
        neighbours = 0

        """
        TODO: Weird bug here, most likely the result of python reusing locations across iterations.
              Workaround is to iterate all neighbours manually...
        """
        neighbours += self.IsAlive(self.GetOffset(-1, -1, self.index), self.check)
        neighbours += self.IsAlive(self.GetOffset(-1, 0, self.index), self.check)
        neighbours += self.IsAlive(self.GetOffset(-1, 1, self.index), self.check)
        neighbours += self.IsAlive(self.GetOffset(0, -1, self.index), self.check)
        neighbours += self.IsAlive(self.GetOffset(0, 1, self.index), self.check)
        neighbours += self.IsAlive(self.GetOffset(1, -1, self.index), self.check)
        neighbours += self.IsAlive(self.GetOffset(1, 0, self.index), self.check)
        neighbours += self.IsAlive(self.GetOffset(1, 1, self.index), self.check)

        current = self.IsAlive(self.index, self.check)

        return current, neighbours

    def CalcGeneration(self, index: int, check: int) -> None:
        """ Calculates current index's state in the next generation. """

        """
        TODO: Current implementation checks all 8 neighbours for every cell, which is slow.
              Using a hash based approach for generation calculation seems like a bettter idea...
        """

        self.index = index
        self.check = check
        self.dest_check = self.GetOppositeCheck(check)

        current, neighbours = self.GetArea()
        if(current == 1 and neighbours in [2, 3]):
            # Any live cell with two or three live neighbours survives.
            return self.Spawn()

        elif(current == 0 and neighbours in [3]):
            # Any dead cell with three live neighbours becomes a live cell.
            self.Spawn()

        else:
            # All other live cells die in the next generation. Similarly, all other dead cells stay dead.
            self.Kill()

    def SetSeed(self, index: int, check: int) -> None:
        """ Set the current index to alive. """

        self.index = index
        self.dest_check = check
        self.Spawn()


class Display(GAME):
    """
    Class used in the Display thread. Asychronously runs with the Overlord thread using GAME.CALC_EVENT
    and GAME.DISPLAY_EVENT.
    """

    CELLS = ["  ", "██"]  # character used to represent dead | alive

    """
    TODO: Implement fancier UI with menus and editors...?

    STATE_RESIZE = 0
    STATE_ARENA = 1
    STATE_MENU = 2
    STATE_EDITOR = 3
    """

    RESIZE_CONTROLS = {curses.KEY_RESIZE: None}

    @staticmethod
    def RunDisplay(stdscr) -> None:
        """ Entry point for Display thread. """

        l.debug("display started")

        curses.curs_set(False)
        curses.start_color()
        stdscr.nodelay(True)
        d = Display(stdscr)
        d.ShowIntro()

        while(True):  # main display loop
            ch = d.stdscr.getch()

            # screen resize events received through KEY_RESIZE
            if(ch in [curses.KEY_RESIZE]):
                curses.update_lines_cols()

            # move cursor
            elif(ch in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_RIGHT, curses.KEY_LEFT]):
                d.UpdatePosYX(ch)

            # TODO: implement clean exit...
            elif(ch in ["q", "Q"]):
                pass

            else:
                pass

            """
            TODO: Implement fancier UI with menus and editors...?
            elif(ch in [" "]):
                #if(d.ShowMenu() is False):
                 #   break
                pass
            """

            d.ShowArena()  # refresh arena_pad

    def __init__(self, stdscr):
        self.check = 0  # current bit index that is read
        self.state = 1  # 0: Resize, 1: Arena, 2: Menu, 3: Editor  # TODO: Implement fancier UI with menus and editors...?
        self.stdscr = stdscr

        self.arena_y = GAME.MAX_Y  # max Y index of arena_pad
        self.arena_x = GAME.MAX_X*2  # max X index of arena_pad
        self.arena_pad = curses.newpad(self.arena_y, self.arena_x)

        self.cursor_y = int(self.arena_y/2) #- int(curses.LINES/2)
        self.cursor_x = int(self.arena_x/2) #- int(curses.COLS/2)

    def ShowIntro(self) -> None:
        """ Shows intro... """

        self.stdscr.nodelay(False)

        #print intro to center of screen
        self.stdscr.addstr(int(curses.LINES/2), int(curses.COLS/2)-22,   "John Conway's Game Of Life by iwakura1ain.")
        self.stdscr.addstr(int(curses.LINES/2)+1, int(curses.COLS/2)-22, "        Press any key to start...")
        self.stdscr.getch()

        self.stdscr.nodelay(True)
        self.stdscr.clear()

    def ShowArena(self) -> None:
        """ Shows the arena based on updated shared memory or updated cursor position. """

        if(self.DISPLAY_EVENT.is_set()):
            l.debug("display event received, updating arena")
            self.arena_pad.clear()
            self.UpdateArena()  # read next generation from shared memory
            self.DISPLAY_EVENT.clear()
            self.CALC_EVENT.set()
            l.debug("arena updated, calc event set")

        else:
            #l.debug("display event not received")
            pass

        self.arena_pad.refresh(self.cursor_y, self.cursor_x, 0,0, curses.LINES-3, curses.COLS-3)

    def GetNextCell(self) -> tuple[int, int, str]:
        """ Generator that reads the shared memory and yields the y position | x position | state of every cell.  """

        index = 0
        x, y = 0, 0
        while(index < GAME.MAX_INDEX):
            yield y, x, self.CELLS[self.IsAlive(index, self.check)]

            index += 1
            if(int(index/GAME.MAX_X) > y):  # new line
                x = 0
                y += 1
            else:  # current line
                x += 2

    def UpdateArena(self) -> None:
        """ Iterates through GetNextCell() and adds the cells to arena_pad. """

        for y, x, cell in self.GetNextCell():
            try:
                self.arena_pad.addstr(y, x, cell)
            except:
                l.debug("display coordinates wrong")

        self.check = self.GetOppositeCheck(self.check)  # swaps the check index after every generation

    def UpdatePosYX(self, ch: chr) -> None:
        """ Updates the cursor position when the arrow keys are pressed. """

        # cursor scroll amount for each arrow key
        arrow_controls = {curses.KEY_UP: [-3, 0],
                          curses.KEY_DOWN: [3, 0],
                          curses.KEY_RIGHT: [0, 6],
                          curses.KEY_LEFT: [0, -6]}


        # TODO: Cursor scroll limit is kind of bugged, must fix... :(

        # Y axis scroll limit
        if((0 <= self.cursor_y + arrow_controls[ch][0])
           and (self.cursor_y + curses.LINES + arrow_controls[ch][0] < self.arena_y)):
            self.cursor_y += arrow_controls[ch][0]

        # X axis scroll limit
        if((0 <= self.cursor_x + arrow_controls[ch][1])
           and (self.cursor_x + curses.COLS + arrow_controls[ch][1] < self.arena_x)):
            self.cursor_x += arrow_controls[ch][1]


def main(stdscr):
    # create Overlord class, initialize thread pool
    o = Overlord(cpu_count())
    l.debug("overlord started")

    curses.initscr()

    # TODO: Placeholder for a seed file selection...
    o.SeedRand()
    #o.SeedChildren()

    # start display thread
    d = Thread(target=Display.RunDisplay, args=(stdscr,))
    d.start()

    # main game loop
    while(True):
        l.debug("========= generation start ===========")

        # calculate next generation
        o.RunChildren()

        l.debug("========= generation finish ==========")

    # TODO: implement a clean exit
    o.JoinChildren()


if __name__ == "__main__":
    wrapper(main)
