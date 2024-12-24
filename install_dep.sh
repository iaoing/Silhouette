#!/bin/bash
sudo apt update
sudo apt-get -y install build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
sudo apt-get -y install python3-pip
sudo apt-get -y install qemu-system-x86
sudo apt-get -y install memcached
pip3 install pymemcache memcache psutil pytz qemu.qmp intervaltree aenum netifaces prettytable tqdm numpy matplotlib