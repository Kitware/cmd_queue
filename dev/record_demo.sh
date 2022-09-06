#sudo apt-get install imagemagick ttyrec gcc x11-apps make git -y
cd "$HOME"/code
git clone https://github.com/icholy/ttygif.git
cd ttygif
PREFIX=$HOME/.local make 
PREFIX=$HOME/.local make install


ttyrec mydemo
xdoctest -m cmd_queue.tmux_queue TMUXMultiQueue.monitor:1 --interact
ttygif mydemo -f
