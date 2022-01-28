#!/usr/bin/python3

from copy import copy

from multiprocessing.managers import SharedMemoryManager
from multiprocessing import Event

import logging as l


# logging configuration 
l.basicConfig(level=l.DEBUG, filename="log.txt", filemode="w", format='%(message)s')


class GAME:
    """ Global class inherited across all classes. Access to shared memory, events, and max lengths. """

    # dimentions of arena
    MAX_Y = 300  # Y axis length of arena
    MAX_X = 300  # X axis length of arena
    MAX_INDEX = MAX_X * MAX_Y  # index length of shared memory

    # shared memory manager process
    #SHM_MANAGER = SharedMemoryManager()
    #SHM_MANAGER.start()
    SHM_MANAGER = None

    # singular shared memory identifier
    #ARENA_SHM = SHM_MANAGER.SharedMemory(size=MAX_INDEX)
    #ARENA = ARENA_SHM.buf
    ARENA_SHM = None
    ARENA = None

    # event for calculation start
    #CALC_EVENT = Event()
    #CALC_EVENT.set()
    CALC_EVENT = None

    # event for display read start
    #DISPLAY_EVENT = Event()
    #DISPLAY_EVENT.clear()
    DISPLAY_EVENT = None

    @classmethod
    def InitSharedMemory(cls):
        cls.SHM_MANAGER = SharedMemoryManager()
        cls.SHM_MANAGER.start()

        cls.ARENA_SHM = cls.SHM_MANAGER.SharedMemory(size=cls.MAX_INDEX)
        cls.ARENA = cls.ARENA_SHM.buf

    @classmethod
    def SetSharedMemory(cls, arena_shm):
        cls.ARENA_SHM = arena_shm
        cls.ARENA = arena_shm.buf    

    @classmethod
    def InitEvents(cls):
        cls.CALC_EVENT = Event()
        cls.CALC_EVENT.set()

        cls.DISPLAY_EVENT = Event()
        cls.DISPLAY_EVENT.clear()

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









