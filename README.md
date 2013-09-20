wrats
=====

Web Restricted Access To Server - allow file viewing, editing and execution without shell access

Introduction
------------

Suppose you want other people to be able to read, edit or execute files on your server, but
you don't want to give them shell access. Or you want to have a set of scripts available via
your browser.

This tool, wrats, is a simple website that allows you to do so. It consists of 2 main files:

- wrats.cgi
- wrats.conf

The file wrats.cgi contains the whole website. It is configurable via wrats.conf, which is a JSON
config file that lists exactly what is allowed. These two files must be in the same dir.

Then there is wrats.css, which is a stylesheet to make the website look better.

Installation
------------

The installation process consists of the following steps:

- put wrats.cgi and wrats.conf in a dir that allows CGI execution
- if necessary, install JSON.pm via your favourite package manager
- make sure that wrats.cgi is executable for the web user
- edit wrats.conf
- optionally, put wrats.css in a web readable dir

For example, in Ubuntu with apache installed, you could do the following:

    sudo apt-get install libjson-perl
    cd ~/src
    git clone https://github.com/joostvunderink/wrats.git
    cd wrats
    cp wrats.conf.example wrats.conf
    $EDITOR wrats.conf
    sudo cp wrats.cgi wrats.conf /usr/lib/cgi-bin/
    sudo mkdir /var/www/css
    sudo cp wrats.css /var/www/css

In wrats.conf, the CSS file location would be "/css/wrats.css". This would make wrats available
via http://your.servers.hostname/cgi-bin/wrats.cgi

Security
--------

wrats has been written with security in mind. Before any file access is done, the requested filename
is string compared to the allowed filenames in the config. Because of that, tricks like putting %00
in the filename, or using '../../../../../etc/passwd', will not work.

There is also a check that makes sure that it is not possible to both edit and execute the same file
via wrats. This would allow the user to execute arbitrary code. If you put the same filename in both
the edit_file and execute_file sections of the config, wrats will refuse to run.

Authentication
--------------

wrats itself does not have authentication. If you want authentication, I suggest you setup
your http server to do that (e.g. via .htaccess).


