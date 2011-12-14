# Git Pull Request

Git command to automate many common tasks involving pull requests.

Based on scripts by Connor McKay<connor.mckay@liferay.com>, Andreas Gohr <andi@splitbrain.org>, Minchau Dang<minchau.dang@liferay.com> and Nate Cavanaugh<nathan.cavanaugh@liferay.com>.

## Install

1.	First clone this repository to a directory of your choice.

		$ git clone git://github.com/greneholt/git-pull-request.git

2.	Then edit your bash profile and add the following line:

		alias gitpr="source YOUR_DIRECTORY/git-pull-request/git-pull-request.sh"
	
3.	Go to <https://github.com/account/admin> to find your API token. Then edit
	your `.gitconfig` file and add the following:

		[github]
			user = your github username
			token = your github API token

4.	Change into a local git repository and try it out! To see a list of all open
	pull requests on your repository, run:

		gitpr
		
	To see a list of all possible commands, run:
	
		gitpr help