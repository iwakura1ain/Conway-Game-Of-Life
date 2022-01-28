#!/usr/bin/python3
"""
John Conway's Game Of Life implemented in python by iwakura1ain. 
"""
__author__ = "https://github.com/iwakura1ain"
__version__ = "WIP"

import Game
from Game import l
import Execute
import Display

from curses import wrapper

        
def main(stdscr):    
    # create Overlord class, initialize process pool
    o = Execute.Overlord()
    l.debug("overlord created")

    d = Display.Display(stdscr)
    l.debug("display created")

    Game.GAME.InitSharedMemory()
    Game.GAME.InitEvents()

    o.SeedRand()
    #o.SeedChildren()

    d.RunDisplayThread()

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







