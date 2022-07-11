#!/bin/bash
flake8 ./cmd_queue --count --select=E9,F63,F7,F82 --show-source --statistics
