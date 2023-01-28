__doc__='

Requires:
    sudo apt-get install imagemagick ttyrec gcc x11-apps make git -y

    cd "$HOME"/code
    git clone https://github.com/icholy/ttygif.git
    cd ttygif
    PREFIX=$HOME/.local make 
    PREFIX=$HOME/.local make install

'


export WINDOWID=$(xdotool getwindowfocus)
echo "WINDOWID = $WINDOWID"
xwininfo -id "$WINDOWID"
xdotool windowsize "$WINDOWID" 811 501
cls

ttyrec cmd_queue_demo_rec -e "INTERACTIVE_TEST=1 xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.monitor:1; exit"

# Optional: can replay the sequence
ttyplay cmd_queue_demo_rec

ttygif cmd_queue_demo_rec -f
