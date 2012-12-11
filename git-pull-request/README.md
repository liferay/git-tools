# Git Pull Request

Git command to automate many common tasks involving pull requests.

Based on scripts by Connor McKay<connor.mckay@liferay.com>, Andreas Gohr <andi@splitbrain.org>, Minhchau Dang<minhchau.dang@liferay.com> and Nate Cavanaugh<nathan.cavanaugh@liferay.com>.

## Install

1.	First clone this repository to a directory of your choice.

		$ git clone git://github.com/liferay/git-tools.git

2.	Then edit your bash profile and add the following line:

		alias gitpr="source YOUR_DIRECTORY/git-tools/git-pull-request/git-pull-request.sh"

3.	Go to <https://github.com/account/admin> to find your API token. Then edit your `.gitconfig` file and add the following:

		[github]
			user = your github username
			token = your github API token

4.	Change into a local git repository and try it out! To see a list of all open pull requests on your repository, run:

		gitpr

	To see a list of all possible commands, run:

		gitpr help

5. If you want to use the "user aliases" functionality you need to configure your git repo with:

		git config git-pull-request.users-alias-file PATH_TO_YOUR_FILE (local to the current repo)

		git config --global git-pull-request.users-alias-file PATH_TO_YOUR_FILE (global for all the git repos)

   Run the command gitpr update-users. This command will populate the previous file with all the info of the users who has forked your upstream repository