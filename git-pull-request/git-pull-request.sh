#!/bin/bash

# Add an alias for this script to your bash profile as follows:
# alias gitpr="source YOUR_DIRECTORY/git-pull-request/git-pull-request.sh"

> /tmp/git-pull-request-chdir

PR=`dirname "$BASH_SOURCE"`
"$PR/git-pull-request.py" "$@"

DIR=`cat /tmp/git-pull-request-chdir`

if [ -n "$DIR" ]; then
	cd $DIR
fi
