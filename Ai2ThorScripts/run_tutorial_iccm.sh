#!/bin/bash
python /Users/jongchan/Dropbox/EmbodiedAI/codes/flask_server.py &  # Run Flask in background
sleep 3 # Wait for Flask to start
python /Users/jongchan/Dropbox/EmbodiedAI/codes/keyboard_player_tutorial_iccm.py  # Run test script

