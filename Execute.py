#!/usr/bin/python3

from Game import GAME 

from os import cpu_count
from itertools import repeat
from copy import copy

from random import randrange

from multiprocessing import Pool

import logging as l


class Overlord(GAME):
    """
    Process pool controller that manages jobs sent to children as well as signal events between the display thread.
    """

    def __init__(self, child_num: int = cpu_count()):
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
                                         zip(repeat(GAME.ARENA_SHM),
                                             range(GAME.MAX_INDEX),
                                             repeat(self.check)),
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
                                         zip(repeat(GAME),
                                             filter(lambda i: i is not None, seed_index),
                                             repeat(self.check)),
                                         chunksize=30)

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
    def SeedChild(template, index: int, check: int) -> None:
        """ Process entry point for Overlord.SeedRand(). """

        current = Child()
        current.SetSeed(index, check)

    @staticmethod
    def RunChild(game, index: int, check: int) -> None:
        """ Process entry point for Overlord.RunChildren(). """

        current = Child()
        current.CalcGeneration(index, check)

    def __init__(self):
        self.index = None  # Current index being calculated
        self.check = None  # Bit index being read
        self.dest_check = None  # Bit index being written
        #GAME.SetSharedMemory(shm)

    def Spawn(self) -> None:
        """ Set current cell bit to 1. """

        try:
            temp = copy(self.ARENA[self.index])
            self.ARENA[self.index] = temp | (1 << self.dest_check)
            return True

        except IndexError:
            pass

    def Kill(self) -> None:
        """ Set current cell bit to 0. """

        try:
            temp = copy(self.ARENA[self.index])
            self.ARENA[self.index] = temp & ~(1 << self.dest_check)
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






