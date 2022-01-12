#!/usr/bin/python3

#import numpy as np

from os import cpu_count
from itertools import repeat
from time import sleep
from copy import copy
from random import randrange

from multiprocessing import Pool
from multiprocessing.managers import SharedMemoryManager

import curses
from curses import wrapper


class GAME:
    MAX_Y = 100
    MAX_X = 100
    MAX_INDEX = MAX_X * MAX_Y
    ARENA_NAME = "GameOfLife"
    SEED_FILE = "test.seed"
    
    def GetXaxis(self, x, current):
        if(self.MAX_X * int(current/self.MAX_X) <= current + x < self.MAX_X * int(current/self.MAX_X + 1)):
            return current + x
        
        else:
            raise IndexError
            
    def GetYaxis(self, y, current):
        if(0 <= current + y*self.MAX_X < self.MAX_INDEX):
            return current + y*self.MAX_X
        
        else:
            raise IndexError
        
    def GetOffset(self, x, y, current):
        try:
            current = self.GetXaxis(x, current)
            current = self.GetYaxis(y, current)
            return current
        
        except IndexError:
            return None
    
class Overlord(GAME):
    def __init__(self, child_num=cpu_count()):
        self.timer = None #TODO: Implement timer
        self.generation = 0            
        self.check = 0
        self.temp = 1
        
        self.shm_manager = SharedMemoryManager()
        self.shm_manager.start()
        
        self.arena_shm = self.shm_manager.SharedMemory(size=self.MAX_INDEX)
        self.arena = self.arena_shm.buf

        self.child_num = child_num
        self.child_pool = Pool(processes=self.child_num)        

        
    def RunChildren(self):
        #call child with args (index, check, arena_shm)
        return self.child_pool.starmap(RunChild, zip(range(self.MAX_INDEX),
                                                     repeat(self.check),
                                                     repeat(self.arena_shm)))

    
    
    def SwapCheck(self):
        self.generation += 1
        self.check, self.temp = self.temp, self.check
        return self.check
        
    def JoinChildren(self):
        self.shm_manager.shutdown()

        self.child_pool.close()
        self.child_pool.join()    
        
    def SeedRand(self):
        for i in [randrange(0, self.MAX_INDEX) for j in range(self.MAX_INDEX)]:
            temp = copy(self.arena[i])
            self.arena[i] = temp | (1 << self.check)

    def SeedFile(self, x=0, y=0):
        seed_index = []
        
        with open(self.SEED_FILE, "r") as fd: #TODO: cleanup needed
            lines = fd.readlines()
            for linum, line in enumerate(lines):
                for i, c in enumerate(line):
                    if(c == "O"):
                        index = self.GetOffset(x+i, y+linum, 0)
                        if(i is not None):
                            seed_index.append(index)
                        
        #call child with args (seed_index, check, arena_shm)
        return self.child_pool.starmap(SeedChildren, zip(seed_index,
                                                         repeat(self.check),
                                                         repeat(self.arena_shm)))

def SeedChildren(index, check, shm):
        current = Child(index, check, shm)
        state = current.SetSeed()
        
        return state
        
def RunChild(index, check, shm):
    #resource_tracker.unregister(shm._name, "shared_memory")
        
    current = Child(index, check, shm)
    state = current.CalcGeneration()
    
    return index, current.IsAlive(current.index), current.neighbour_cnt, state

class Child(GAME):
    def __init__(self, index, check, shm):
        self.index = index
        
        #self.arena_shm = shared_memory.SharedMemory(name=self.ARENA_NAME, create=False)
        #self.arena = self.arena_shm.buf
        self.arena_shm = shm
        self.arena = self.arena_shm.buf
                
        self.check = check
        self.neighbour_cnt = self.GetNeighbors()
        
    def DestCheck(self):
        if(self.check == 0):
            return 1
        else:
            return 0
        
    def Spawn(self, dest): # set bit to 1
        try:
            temp = copy(self.arena[self.index])
            self.arena[self.index] = temp | (1 << dest)
            return True
        except IndexError:
            return False
        
        
    def Kill(self, dest): # set bit to 0
        try:
            temp = copy(self.arena[self.index])
            self.arena[self.index] = temp & ~(1 << dest)
            return True
        except IndexError:
            return False
        
    def IsAlive(self, i):
        if(i is None):
            return 0
        else:
            return int((copy(self.arena[i]) >> self.check) & 1)
        
    def GetNeighbors(self):
        count = 0
        # for x in range(-1, 2):
        #     for y in range(-1, 2):
        #         if(x != 0 and y != 0):
        #             count += self.IsAlive(self.GetOffset(x, y))
        
        count += self.IsAlive(self.GetOffset(-1, -1, self.index))
        count += self.IsAlive(self.GetOffset(-1, 0, self.index))
        count += self.IsAlive(self.GetOffset(-1, 1, self.index))
        count += self.IsAlive(self.GetOffset(0, -1, self.index))
        count += self.IsAlive(self.GetOffset(0, 1, self.index))
        count += self.IsAlive(self.GetOffset(1, -1, self.index))
        count += self.IsAlive(self.GetOffset(1, 0, self.index))
        count += self.IsAlive(self.GetOffset(1, 1, self.index))
        
        return count
    
    def CalcGeneration(self):
        if(self.IsAlive(self.index) == 1 and self.neighbour_cnt in [2, 3]):
            # Any live cell with two or three live neighbours survives.
            return self.Spawn(self.DestCheck())
            
        elif(self.IsAlive(self.index) == 0 and self.neighbour_cnt in [3]):
            # Any dead cell with three live neighbours becomes a live cell.
            return self.Spawn(self.DestCheck())
            
        else:
            # All other live cells die in the next generation. Similarly, all other dead cells stay dead.
            return self.Kill(self.DestCheck())
            
        #self.arena_shm.close()

    def SetSeed(self):
        return self.Spawn(self.check)
    
class Display(GAME):    
    CELLS = ["  ", "██"]
    #HIGHLIGHT_COL = curses.init_pair(1, curses.COLOR_RED, curses.COLOR_RED)
    #REGULAR_COL = curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    
    def __init__(self, arena_shm, stdscr):
        self.arena_shm = arena_shm
        self.arena = self.arena_shm.buf
        self.check = 0

        self.stdscr = stdscr
        curses.curs_set(False)
        self.pad = curses.newpad(self.MAX_Y, self.MAX_X*2)
                
    def IsAlive(self, index):
        return (copy(self.arena[index]) >> self.check) & 1

    def GetNextCell(self):
        index = 0
        x, y = 0, 0
        while(index < self.MAX_INDEX):
            yield y, x, self.CELLS[self.IsAlive(index)]

            index += 1
            if(int(index/self.MAX_X) > y):
                x = 0
                y += 1
            else:
                x += 2

                
    
    def RefreshPadContents(self):
        for y, x, cell in self.GetNextCell():
            try: 
                self.pad.addstr(y, x, cell)
            except:
                pass
        
        self.pad.refresh(0,0, 1,2, curses.LINES-1,curses.COLS-1)
            
    # def PrintArenaIndex(self, x, y):
    #     print(f" {bin(self.arena[y*self.MAX_X + x]): <4} ")

    # def PrintResultIndex(self, x, y):
    #     for i in self.pool_result:
    #         if(i[0] == y*self.MAX_X + x):
    #             print(i)
    #             return
            
    # def PrintResult(self):
    #     for y in range(self.MAX_Y):
    #         for x in range(self.MAX_X):
    #             print(self.pool_result[y*self.MAX_X + x])
    #         print("\n", end="")
        
    # def PrintArena(self):
    #     for y in range(self.MAX_Y):
    #         for x in range(self.MAX_X):
    #             #print(f" {bin(self.arena[y*self.MAX_X + x]): <4} ", end="")
    #             if(self.IsAlive(y*self.MAX_X + x) == 1):
    #                 print("O", end="")
    #             else:
    #                 print("X", end="")
    #         print("\n", end="")
            
    #     print("\n", end="")
    #     print("\n", end="")
    
def main(stdscr):
    
    a = Overlord()
    p = Display(a.arena_shm, stdscr)
    
    #a.SeedRand()
    a.SeedFile()
    p.RefreshPadContents()

    while(True):
        p.pool_result = a.RunChildren()
        p.check = a.SwapCheck()
        p.RefreshPadContents()
        sleep(0.1)
        
    a.JoinChildren()
    
if __name__=="__main__":
    wrapper(main)
    

















