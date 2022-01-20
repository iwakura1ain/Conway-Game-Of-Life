#!/usr/bin/python3

#import numpy as np

from os import cpu_count
from itertools import repeat
from time import sleep
from copy import copy
from random import randrange

from multiprocessing import Pool
from multiprocessing.managers import SharedMemoryManager

from threading import Thread

import curses
from curses import wrapper


class GAME:
    MAX_Y = 300
    MAX_X = 300
    MAX_INDEX = MAX_X * MAX_Y
        
    SHM_MANAGER = SharedMemoryManager()
    SHM_MANAGER.start()
        
    ARENA_SHM = SHM_MANAGER.SharedMemory(size=MAX_INDEX)
    ARENA = ARENA_SHM.buf

    def GetXaxis(self, x, current):
        if(GAME.MAX_X * int(current/GAME.MAX_X) <= current + x < GAME.MAX_X * int(current/GAME.MAX_X + 1)):
            return current + x
        
        else:
            raise IndexError
            
    def GetYaxis(self, y, current):
        if(0 <= current + y*GAME.MAX_X < GAME.MAX_INDEX):
            return current + y*GAME.MAX_X
        
        else:
            raise IndexError
        
    def GetOffset(self, x, y, current):
        try:
            current = self.GetXaxis(x, current)
            current = self.GetYaxis(y, current)
            return current
        
        except IndexError:
            return None
        
    def GetOppositeCheck(self, check):
        if(check == 0): return 1
        else: return 0

    def IsAlive(self, index, check): 
        if(index is None):
            return 0
        else:
            return int((copy(GAME.ARENA[index]) >> check) & 1)

    # def Spawn(self, index, check): # set current cell bit to 1
    #     try:
    #         temp = copy(GAME.ARENA[self.index])
    #         GAME.ARENA[self.index] = temp | (1 << self.dest_check)
    #         return True
        
    #     except IndexError:
    #         pass
    
    # def Kill(self, index, check): # set current cell bit to 0
    #     try:
    #         temp = copy(GAME.ARENA[self.index])
    #         GAME.ARENA[self.index] = temp & ~(1 << self.dest_check)
    #         return True
        
    #     except IndexError:
    #         pass
   

class Overlord(GAME):
    def __init__(self, child_num=cpu_count()):
        self.timer = None #TODO: Implement timer
        self.generation = 0            
        self.check = 0
        
        #self.shm_manager = SharedMemoryManager()
        #self.shm_manager.start()
        
        #self.arena_shm = self.shm_manager.SharedMemory(size=GAME.MAX_INDEX)
        #self.arena = self.arena_shm.buf

        self.child_num = child_num
        self.child_pool = Pool(processes=self.child_num)

    def SwapCheck(self):
        temp = self.check
        self.check = self.GetOppositeCheck(self.check)
        return temp

    def SeedRand(self):
        for i in [randrange(0, GAME.MAX_INDEX) for j in range(GAME.MAX_INDEX)]:
            temp = copy(GAME.ARENA[i])
            GAME.ARENA[i] = temp | (1 << self.check)
        
    def RunChildren(self):
        #call RunChild( [[index, check] * chunksize] )
        result = self.child_pool.starmap(RunChild,
                                         zip(range(GAME.MAX_INDEX), repeat(self.check)),
                                         chunksize=30)
        prev_check = self.SwapCheck()
        
        return prev_check
    
    def SeedChildren(self, x=0, y=0):
        seed_index = []
        
        with open("test.seed", "r") as fd: 
            lines = fd.readlines()
            for row, line in enumerate(lines):
                for col, char in enumerate(line):
                    if(char == "O"):
                        seed_index.append(self.GetOffset(x+col, y+row, 0))
                        
        #call SeedChild( [[index, check] * chunksize] )
        result = self.child_pool.starmap(SeedChild,
                                         zip(filter(lambda i: i is not None, seed_index), repeat(self.check)))
    
    def JoinChildren(self):
        try:
            GAME.shm_manager.shutdown()
            GAME.child_pool.close()
            GAME.child_pool.join()
            
        except:
            pass #TODO

# def SeedChild(args):
#     current = Child()
#     for arg in args:
#         current.SetSeed(arg[0], arg[1])

# def RunChild(args):
#     current = Child()
#     for arg in args:
#         current.CalcGeneration(arg[0], arg[1])

def SeedChild(index, check):
    current = Child()
    current.SetSeed(index, check)

def RunChild(index, check):
    current = Child()
    current.CalcGeneration(index, check)
    
class Child(GAME):
    def __init__(self):
        self.index = None
        self.check = None
        self.dest_check = None
    
    def Spawn(self): # set current cell bit to 1
        try:
            temp = copy(GAME.ARENA[self.index])
            GAME.ARENA[self.index] = temp | (1 << self.dest_check)
            return True
        
        except IndexError:
            pass
    
    def Kill(self): # set current cell bit to 0
        try:
            temp = copy(GAME.ARENA[self.index])
            GAME.ARENA[self.index] = temp & ~(1 << self.dest_check)
            return True
        
        except IndexError:
            pass
        
    def GetArea(self):
        current = 0
        neighbours = 0

        #TODO: Weird bug here, most likely python reusing locations across iterations.
        #    Workaround is to iterate all neighbours manually... 
        neighbours += self.IsAlive(self.GetOffset(-1, -1, self.index), self.check )
        neighbours += self.IsAlive(self.GetOffset(-1, 0, self.index), self.check )
        neighbours += self.IsAlive(self.GetOffset(-1, 1, self.index), self.check )
        neighbours += self.IsAlive(self.GetOffset(0, -1, self.index), self.check )
        neighbours += self.IsAlive(self.GetOffset(0, 1, self.index), self.check )
        neighbours += self.IsAlive(self.GetOffset(1, -1, self.index), self.check )
        neighbours += self.IsAlive(self.GetOffset(1, 0, self.index), self.check )
        neighbours += self.IsAlive(self.GetOffset(1, 1, self.index), self.check )
        
        current = self.IsAlive(self.index, self.check )
        
        return current, neighbours
    
    def CalcGeneration(self, index, check):
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
    
    def SetSeed(self, index, check):
        self.index = index
        self.dest_check = check        
        self.Spawn()

# def RunDisplay(display):
#     d = display

#     while(True):
        
    
class Display(GAME):    
    CELLS = ["  ", "██"]
    #HIGHLIGHT_COL = curses.init_pair(1, curses.COLOR_RED, curses.COLOR_RED)
    #REGULAR_COL = curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    
    def __init__(self, stdscr):
        self.check = 0

        self.stdscr = stdscr
        curses.curs_set(False)
        curses.start_color()
        stdscr.nodelay(True)

        self.pad = curses.newpad(GAME.MAX_Y, GAME.MAX_X*2)
        self.pad_coord = [0,0]
        
    def GetNextCell(self):
        index = 0
        x, y = 0, 0
        while(index < GAME.MAX_INDEX):
            yield y, x, self.CELLS[self.IsAlive(index, self.check)]
            
            index += 1
            if(int(index/GAME.MAX_X) > y):
                x = 0
                y += 1
            else:
                x += 2
    
    def RefreshPad(self):
        for y, x, cell in self.GetNextCell():
            try: 
                self.pad.addstr(y, x, cell)
            except:
                pass
        
        self.pad.refresh(0,0, 1,2, curses.LINES-1,curses.COLS-1)
        #self.check = self.GetOppositeCheck(self.check)

    def Intro(self):
        self.stdscr.nodelay(False)

        self.stdscr.addstr(int(curses.LINES/2), int(curses.COLS/2),   "Game Of Life by John Conway")
        self.stdscr.addstr(int(curses.LINES/2)+1, int(curses.COLS/2), "  Press any key to start...")
        self.stdscr.getch()

        self.stdscr.nodelay(True)
        self.stdscr.clear()
            
def main(stdscr):
    o = Overlord()
    d = Display(stdscr)
    
    #o.SeedChildren()
    o.SeedRand()
    d.RefreshPad()
    sleep(1)

    while(True):
        d.check = o.RunChildren()    
        d.RefreshPad()
        #sleep(0.01)
        
    o.JoinChildren()
    
if __name__=="__main__":
    wrapper(main)
    

















