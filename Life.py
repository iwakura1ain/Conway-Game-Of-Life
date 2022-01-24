#!/usr/bin/python3
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
l.basicConfig(level=l.DEBUG, filename="log.txt", filemode="a", format='%(message)s')

class GAME:
    MAX_Y = 300
    MAX_X = 300
    MAX_INDEX = MAX_X * MAX_Y
    
    SHM_MANAGER = SharedMemoryManager()
    SHM_MANAGER.start()
    
    ARENA_SHM = SHM_MANAGER.SharedMemory(size=MAX_INDEX)
    ARENA = ARENA_SHM.buf


    CALC_EVENT = Event()
    CALC_EVENT.set()
    DISPLAY_EVENT = Event()
    DISPLAY_EVENT.clear()
    
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
        if(check == 0):
            return 1
        else:
            return 0

    def IsAlive(self, index, check): 
        if(index is None):
            return 0
        else:
            return int((copy(GAME.ARENA[index]) >> check) & 1)
        
class Overlord(GAME):
    def __init__(self, child_num=cpu_count()):
        self.check = 0
        
        self.child_num = child_num
        self.child_pool = Pool(processes=self.child_num)

    def SwapCheck(self):        
        temp = self.check
        self.check = self.GetOppositeCheck(self.check)
        return temp

    def SeedRand(self):
        l.debug("waiting for calc event")
        self.CALC_EVENT.wait()
        l.debug("calc event received, seeding random")

        for i in [randrange(0, GAME.MAX_INDEX) for j in range(GAME.MAX_INDEX)]:
            temp = copy(GAME.ARENA[i])
            GAME.ARENA[i] = temp | (1 << self.check)

        self.CALC_EVENT.clear()
        self.DISPLAY_EVENT.set()
        l.debug("seed rand finished, display event set")
        
    def RunChildren(self):
        l.debug("waiting for calc event")
        self.CALC_EVENT.wait()
        l.debug("calc event received, running children")
        
        #call RunChild( [[index, check] * chunksize] )
        result = self.child_pool.starmap(Child.RunChild,
                                         zip(range(GAME.MAX_INDEX), repeat(self.check)),
                                         chunksize=30)
        prev_check = self.SwapCheck()
        
        self.CALC_EVENT.clear()
        self.DISPLAY_EVENT.set()
        l.debug("run children finished, display event set")
        
        return prev_check
    
    def SeedChildren(self, x=0, y=0):
        l.debug("waiting for calc event")
        self.CALC_EVENT.wait()
        l.debug("calc event received, seeding children")
        
        seed_index = []
        with open("test.seed", "r") as fd: 
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
    
    def JoinChildren(self):
        self.CALC_EVENT.wait()
        
        try:
            GAME.shm_manager.shutdown()
            GAME.child_pool.close()
            GAME.child_pool.join()
            
        except:
            pass #TODO
        
        self.CALC_EVENT.clear()
        self.DISPLAY_EVENT.set() 
       
class Child(GAME):    
    @staticmethod
    def SeedChild(index, check):
        current = Child()
        current.SetSeed(index, check)

    @staticmethod
    def RunChild(index, check):
        current = Child()
        current.CalcGeneration(index, check)

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

        #TODO: Weird bug here, most likely the result of python reusing locations across iterations.
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


class Display(GAME):    
    CELLS = ["  ", "██"]

    STATE_RESIZE = 0
    STATE_ARENA = 1
    STATE_MENU = 2
    STATE_EDITOR = 3
    
    RESIZE_CONTROLS = {curses.KEY_RESIZE: None}
    
    @staticmethod
    def RunDisplay(stdscr):
        l.debug("display started")
        
        curses.curs_set(False)
        curses.start_color()
        stdscr.nodelay(True)
        d = Display(stdscr)
        d.ShowIntro()
        
        while(True):
            ch = d.stdscr.getch()
            if(ch in [curses.KEY_RESIZE]):
                curses.update_lines_cols()

            elif(ch in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_RIGHT, curses.KEY_LEFT]):
                d.UpdatePosYX(ch)

            elif(ch in [" "]):
                #if(d.ShowMenu() is False):
                 #   break
                pass
            else:
                pass

            d.ShowArena()
                
    def __init__(self, stdscr):
        self.check = 0
        self.state = 1 # 0: Resize, 1: Arena, 2: Menu, 3: Editor 
        self.stdscr = stdscr
        
        self.arena_y = GAME.MAX_Y
        self.arena_x = GAME.MAX_X*2        
        self.arena_pad = curses.newpad(self.arena_y, self.arena_x)
            
        self.cursor_y = int(self.arena_y/2) #- int(curses.LINES/2)
        self.cursor_x = int(self.arena_x/2) #- int(curses.COLS/2)
        
    def ShowIntro(self):
        self.stdscr.nodelay(False)
        
        self.stdscr.addstr(int(curses.LINES/2), int(curses.COLS/2)-13,   "Game Of Life by John Conway")
        self.stdscr.addstr(int(curses.LINES/2)+1, int(curses.COLS/2)-13, "  Press any key to start...")
        self.stdscr.getch()
        
        self.stdscr.nodelay(True)
        self.stdscr.clear()
            
    def ShowArena(self):
        if(self.DISPLAY_EVENT.is_set()):
            l.debug("display event received, updating arena")
            self.arena_pad.clear()
            self.UpdateArena()
            self.DISPLAY_EVENT.clear()
            self.CALC_EVENT.set()
            l.debug("arena updated, calc event set")
            
        else:
            l.debug("display event not received")
            
        self.arena_pad.refresh(self.cursor_y, self.cursor_x, 0,0, curses.LINES-3, curses.COLS-3)

    # def ShowMenu(self):
    #     self.menu_pad = curses.newpad()
        
    #     while(True):
    #         ch = self.stdscr.getch
                    
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
    
    def UpdateArena(self):
        for y, x, cell in self.GetNextCell():
            try: 
                self.arena_pad.addstr(y, x, cell)
            except:
                pass
            
        self.check = self.GetOppositeCheck(self.check)

    def UpdatePosYX(self, ch):
        arrow_controls = {curses.KEY_UP: [-3, 0],
                          curses.KEY_DOWN: [3, 0],
                          curses.KEY_RIGHT: [0, 6],
                          curses.KEY_LEFT: [0, -6]}
        
        if((0 <= self.cursor_y + arrow_controls[ch][0])
           and (self.cursor_y + curses.LINES + arrow_controls[ch][0] < self.arena_y)):
            self.cursor_y += arrow_controls[ch][0]
            
        if((0 <= self.cursor_x + arrow_controls[ch][1])
           and (self.cursor_x + curses.COLS + arrow_controls[ch][1] < self.arena_x)):
            self.cursor_x += arrow_controls[ch][1]

        
def main(stdscr):
    o = Overlord()
    l.debug("overlord started")
    o.SeedRand()
    
    d = Thread(target=Display.RunDisplay, args=(stdscr,))
    d.start()
    
    while(True):
        l.debug("========= generation start ===========")
        o.RunChildren()
        l.debug("========= generation finish ==========")
        
    o.JoinChildren()
    
if __name__=="__main__":
    wrapper(main)
    

















