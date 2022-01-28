#!/usr/bin/python3

from Game import GAME

from threading import Thread

import curses

import logging as l


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
    def RunDisplay(display) -> None:
        """ Entry point for Display thread. """
        
        l.debug("display started")
        
        curses.curs_set(False)
        curses.start_color()
        display.stdscr.nodelay(True)
        
        while(True):  # main display loop
            ch = display.stdscr.getch()

            # screen resize events received through KEY_RESIZE
            if(ch in [curses.KEY_RESIZE]):
                curses.update_lines_cols()

            # move cursor
            elif(ch in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_RIGHT, curses.KEY_LEFT]):
                display.UpdatePosYX(ch)

            # TODO: implement clean exit...
            elif(ch in ["q", "Q"]):
                pass

            else:
                pass

            display.ShowArena()  # refresh arena_pad

    def __init__(self, stdscr):        
        self.check = 0  # current bit index that is read
        self.state = 1  # 0: Resize, 1: Arena, 2: Menu, 3: Editor  # TODO: Implement fancier UI with menus and editors...?
        self.stdscr = stdscr

        self.arena_y = GAME.MAX_Y  # max Y index of arena_pad
        self.arena_x = GAME.MAX_X*2  # max X index of arena_pad
        self.arena_pad = curses.newpad(self.arena_y, self.arena_x)
        
        self.cursor_y = int(self.arena_y/2) #- int(curses.LINES/2)
        self.cursor_x = int(self.arena_x/2) #- int(curses.COLS/2)

        self.display_thread = Thread(target=Display.RunDisplay, args=(self,))

    def RunDisplayThread(self):
        self.display_thread.start()

    
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





