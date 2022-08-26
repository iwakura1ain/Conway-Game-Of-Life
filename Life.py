#!/usr/bin/python3
"""
John Conway's Game Of Life implemented in python by iwakura1ain. 
"""
__author__ = "https://github.com/iwakura1ain"
__version__ = "WIP"

import Game
import Execute
import Display

from curses import wrapper

import logging as l

# logging configuration 
l.basicConfig(level=l.DEBUG, filename="log.txt", filemode="w", format='%(message)s')

        
def main(stdscr):    
    # create Overlord class, initialize process pool
    
    #Game.GAME.InitSharedMemory()
    #Game.GAME.InitEvents()

    o = Execute.Overlord()
    l.debug("overlord created")

    d = Display.Display(stdscr)
    l.debug("display created")



    
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







