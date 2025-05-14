#!/bin/bash
python /Users/jongchan/Dropbox/EmbodiedAI/ICCM2025/flask_server.py &  # Run Flask in background
sleep 3 # Wait for Flask to start
python /Users/jongchan/Dropbox/EmbodiedAI/ICCM2025/keyboard_player_exploration.py # Run test script

