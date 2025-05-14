#!/bin/bash
python flask_server.py &  # Run Flask in background
sleep 3  # Wait for Flask to start
python keyboard_player_master_iccm.py # Run test script

