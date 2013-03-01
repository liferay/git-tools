#!/usr/bin/env python

"""
Git command to automate many common tasks involving pull requests.

Usage:

	gitpr [<options>] <command> [<args>]

Options:

	-h, --help
		Display this message.

	-r <repo>, --repo <repo>
		Use this github repo instead of the 'remote origin' or 'github.repo'
		git config setting. This can be either a remote name or a full
		repository name (user/repo).

	-u <reviewer>, --reviewer <reviewer>
		Send pull requests to this github repo instead of the 'remote upstream'
		or 'github.reviewer' git config setting. This can be either a username
		or a full repository name (user/repo).

	-b <branch>, --update-branch <branch>
		Specify the target branch on the reviewer github repository to submit the pull request.

Commands:

	#no command#
		Displays a list of the open pull requests on this repository.

	#no command# <pull request ID>
		Performs a fetch.

	alias <name> <githubname>
		Create an alias for the github name so you can use it in your git-pr submit
		command.

	close [<comment>]
		Closes the current pull request on github and deletes the pull request
		branch.

	continue-update, cu
		Continues the current update after conflicts have been fixed.

	fetch <pull request ID>
		Fetches the pull request into a local branch, optionally updating it
		and checking it out.

	fetch-all
		Fetches all open pull requests into local branches.

	help
		Displays this message.

	info
		Displays a list of all the user's github repositories and the number
		of pull requests open on each.

	info-detailed
		Displays the same information as "info" but also lists the pull requests for each one (by user)

	merge
		Merges the current pull request branch into the update-branch and deletes the
		branch.

	open [<pull request ID>]
		Opens either the current pull request or the specified request on
		github.

	pull
		Pulls remote changes from the other user's remote branch into the local
		pull request branch.

	show-alias <alias>
		Shows the github username pointed by the indicated alias.

	stats
		Fetches all open pull requests on this repository and displays them along
		with statistics about the pull requests and how many changes (along with how many
		changes by type).

	submit [<pull body>] [<pull title>]
		Pushes a branch and sends a pull request to the user's reviewer on
		github.

	update [<pull request ID or branch name>]
		Updates the current pull request or the specified request with the local
		changes in the update-branch, using either a rebase or merge.

	update-users
		Updates the file configured in git-pull-request.users-alias-file variable. This file contains all the
		github names indexed by the email (without the @ email suffix).


Copyright (C) 2011 Liferay, Inc. <http://liferay.com>

Based on scripts by:
Connor McKay<connor.mckay@liferay.com>
Andreas Gohr <andi@splitbrain.org>
Minhchau Dang<minhchau.dang@liferay.com>
Nate Cavanaugh<nathan.cavanaugh@liferay.com>
Miguel Pastor<miguel.pastor@liferay.com>

Released under the MIT License.
"""

import base64
import getopt
import json
import os
import re
import sys
import urllib
import urllib2
import urlparse
import getpass
import tempfile
# import isodate
# from datetime import date

# Connecting through a proxy,
# requires: socks.py from http://socksipy.sourceforge.net/ next to this file

#import socket
#import socks

#socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "localhost", 8181)
#socket.socket = socks.socksocket

from textwrap import fill

options = {
	'debug-mode': False,
	# Color Scheme
	'color-success': 'green',
	'color-status': 'blue',
	'color-error': 'red',
	'color-warning': 'red',
	'color-display-title-url': 'cyan',
	'color-display-title-number': 'magenta',
	'color-display-title-text': 'red',
	'color-display-title-user': 'blue',
	'color-display-info-repo-title': 'default',
	'color-display-info-repo-count': 'magenta',
	'color-display-info-total-title': 'green',
	'color-display-info-total-count': 'magenta',

	# Disable the color scheme
	'enable-color': True,

	# Sets the default comment to post when closing a pull request.
	'close-default-comment': None,

	# Determines whether fetch will automatically checkout the new branch.
	'fetch-auto-checkout': False,

	# Determines whether to automatically update a fetched pull request branch.
	# Setting this option to true will also cause the new branch to be checked
	# out.
	'fetch-auto-update': False,

	# Whether to show pull requests for the entire repo or just the update-branch.
	'filter-by-update-branch': True,

	# Determines whether to automatically close pull requests after merging
	# them.
	'merge-auto-close': True,

	# Sets the branch to use where updates are merged from or to.
	'update-branch': 'master',

	# Sets the method to use when updating pull request branches with changes
	# in the update-branch.
	# Possible options: 'merge', 'rebase'
	'update-method': 'merge',

	# The organization to update users from (set to None or an empty string to update from the current fork)
	'user-organization': 'liferay',

	# Determines whether to open newly submitted pull requests on github
	'submit-open-github': True,

	# Sets a directory to be used for performing updates to prevent
	# excessive rebuilding by IDE's. Warning: This directory will be hard reset
	# every time an update is performed, so do not do any work other than
	# conflict merges in the work directory.
	'work-dir': None
}

URL_BASE = "https://api.github.com/%s"
SCRIPT_NOTE = 'GitPullRequest Script (by Liferay)'
TMP_PATH = tempfile.gettempdir() + '/%s'

MAP_RESPONSE = {}

def authorize_request(req, token=None, auth_type="token"):
	"""Add the Authorize header to the request"""

	if token == None:
		token = auth_token

	req.add_header("Authorization", "%s %s" % (auth_type, token))

def build_branch_name(pull_request):
	"""Returns the local branch name that a pull request should be fetched into"""
	ref = pull_request['head']['ref']

	request_id = pull_request['number']

	m = re.search("[A-Z]{3,}-\d+", ref)

	branch_name = 'pull-request-%s' % request_id

	if m != None and m.group(0) != '':
		branch_name = '%s-%s' % (branch_name, m.group(0))

	return branch_name

def build_pull_request_title(branch_name):
	"""Returns the default title to use for a pull request for the branch with
	the name"""

	m = re.search("([A-Z]{3,}-\d+)", branch_name)

	if m is not None and m.group(1) != '':
		return m.group(1)

	return branch_name

def chdir(dir):
	f = open(get_tmp_path('git-pull-request-chdir'), 'wb')
	f.write(dir)
	f.close()

def close_pull_request(repo_name, pull_request_ID, comment = None):
	default_comment = options['close-default-comment']

	if comment is None:
		comment = default_comment

	if comment is None or comment == default_comment:
		try:
			f = open(get_tmp_path('git-pull-request-treeish-%s' % pull_request_ID), 'r')
			branch_info = json.load(f)
			f.close()

			username = branch_info['username']

			updated_parent_commit = ''
			updated_head_commit = ''
			original_parent_commit = ''
			original_head_commit = ''

			if 'original' in branch_info:
				original = branch_info['original']
				original_parent_commit = original['parent_commit']
				original_head_commit = original['head_commit']

			if 'updated' in branch_info:
				updated = branch_info['updated']
				updated_parent_commit = updated['parent_commit']
				updated_head_commit = updated['head_commit']

			current_head_commit = os.popen('git rev-parse HEAD').read().strip()[0:10]

			my_diff_comment = ''

			diff_commit = False

			if original_head_commit != current_head_commit:
				current_diff_tree = os.popen('git diff-tree -r -c -M -C --no-commit-id HEAD').read().strip()
				original_diff_tree = os.popen('git diff-tree -r -c -M -C --no-commit-id %s' % original_head_commit).read().strip()

				current_tree_commits = current_diff_tree.split('\n')
				original_tree_commits = original_diff_tree.split('\n')

				if len(current_tree_commits) == len(original_tree_commits):
					for index, commit in enumerate(current_tree_commits):
						current_commits = commit.split(' ')
						original_commits = original_tree_commits[index].split(' ')

						if len(current_commits) >= 4 and len(original_commits) >= 4 and current_commits[3] != original_commits[3]:
							diff_commit = True
							break
				else:
					diff_commit = True

			if (updated_head_commit or original_head_commit) == current_head_commit:
				diff_commit = False

			if diff_commit:
				my_diff_comment = "\n\nView just my changes: https://github.com/%s/compare/%s:%s...%s" % (repo_name, username, updated_head_commit or original_head_commit, current_head_commit)

			if comment is None:
				comment = ''

			new_pr_url = meta('new_pr_url')

			if new_pr_url and new_pr_url != '':
				comment += "\nPull request submitted at: %s" % new_pr_url

			comment += my_diff_comment

			comment += "\nView total diff: https://github.com/%s/compare/%s...%s" % (repo_name, (updated_parent_commit or original_parent_commit), current_head_commit)
		except Exception:
			pass

	if comment is not None and comment != '':
		post_comment(repo_name, pull_request_ID, comment)

	url = get_api_url("repos/%s/pulls/%s" % (repo_name, pull_request_ID))

	params = {
		'state': 'closed'
	}

	github_json_request(url, params)

def color_text(text, token, bold = False):
	"""Return the given text in ANSI colors"""

	# http://travelingfrontiers.wordpress.com/2010/08/22/how-to-add-colors-to-linux-command-line-output/

	if options['enable-color'] == True:
		color_name = options["color-%s" % token]

		if color_name == 'default' or not sys.stdout.isatty():
			return text

		colors = (
			'black', 'red', 'green', 'yellow',
			'blue', 'magenta', 'cyan', 'white'
		)

		if color_name in colors:
			return u"\033[{0};{1}m{2}\033[0m".format(
				int(bold),
				colors.index(color_name) + 30,
				text)
		else:
			return text
	else:
		return text

def command_alias(alias, githubname, filename):
	try:
		users[alias] = githubname
	except Exception:
		raise UserWarning('Error while updating the alias for %s' % alias)

	github_users_file = open(filename, 'w')
	json.dump(users, github_users_file)

	github_users_file.close()

def command_fetch(repo_name, pull_request_ID, auto_update = False):
	"""Fetches a pull request into a local branch"""

	print color_text("Fetching pull request", 'status')
	print

	pull_request = get_pull_request(repo_name, pull_request_ID)
	display_pull_request(pull_request)
	branch_name = fetch_pull_request(pull_request)

	parent_commit = pull_request['base']['sha']
	head_commit = pull_request['head']['sha']
	username = pull_request['user']['login']

	branch_info = {
		'username': username,
		'original': {
			'parent_commit': parent_commit[0:10],
			'head_commit': head_commit[0:10],
		}
	}

	f = open(get_tmp_path('git-pull-request-treeish-%s' % pull_request_ID), 'w')
	branch_treeish = json.dump(branch_info, f)
	f.close()

	if auto_update:
		update_branch(branch_name)
	elif options['fetch-auto-checkout']:
		ret = os.system('git checkout %s' % branch_name)
		if ret != 0:
			raise UserWarning("Could not checkout %s" % branch_name)

	print
	print color_text("Fetch completed", 'success')
	print
	display_status()

def command_close(repo_name, comment = None):
	"""Closes the current pull request on github with the optional comment, then
	deletes the branch."""

	print color_text("Closing pull request", 'status')
	print

	branch_name = get_current_branch_name()
	pull_request_ID = get_pull_request_ID(branch_name)
	pull_request = get_pull_request(repo_name, pull_request_ID)

	display_pull_request(pull_request)

	close_pull_request(repo_name, pull_request_ID, comment)

	update_branch_option = options['update-branch']

	ret = os.system('git checkout %s' % update_branch_option)
	if ret != 0:
		raise UserWarning("Could not checkout %s" % update_branch_option)

	print color_text("Deleting branch %s" % branch_name, 'status')
	ret = os.system('git branch -D %s' % branch_name)
	if ret != 0:
		raise UserWarning("Could not delete branch")

	print
	print color_text("Pull request closed", 'success')
	print
	display_status()

def command_continue_update():
	print color_text("Continuing update from %s" % options['update-branch'], 'status')

	continue_update()
	print
	display_status()

def command_fetch_all(repo_name):
	"""Fetches all pull requests into local branches"""

	print color_text("Fetching all pull requests", 'status')
	print

	pull_requests = get_pull_requests(repo_name, options['filter-by-update-branch'])

	for pull_request in pull_requests:
		fetch_pull_request(pull_request)
		display_pull_request_minimal(pull_request)
		print

	display_status()

def command_help():
	print __doc__

def command_info(username, detailed = False):
	print color_text("Loading information on repositories for %s" % username, 'status')
	print

	# Change URL depending on if info user is passed in

	if username == DEFAULT_USERNAME:
		url = "user/repos"
	else:
		url = "users/%s/repos" % username

	url = get_api_url(url)

	repos = github_json_request(url)

	total = 0

	current_base_name = ''

	for pull_request_info in repos:
		issue_count = pull_request_info['open_issues']

		if issue_count > 0:
			base_name = pull_request_info['name']

			if base_name != current_base_name:
				current_base_name = base_name
				print ""
				print '%s:' % color_text(base_name, 'display-title-text')
				print "---------"

			repo_name = "%s/%s" % (pull_request_info['owner']['login'], base_name)

			print "  %s: %s" % (color_text(base_name, 'display-info-repo-title'), color_text(issue_count, 'display-info-repo-count'))

			if detailed:
				pull_requests = get_pull_requests(repo_name, False)

				current_branch_name = ''

				for pull_request in pull_requests:
					branch_name = pull_request['base']['ref']
					if branch_name != current_branch_name:
						current_branch_name = branch_name
						print ""
						print '    %s:' % color_text(current_branch_name, 'display-title-user')

					print "        %s" % display_pull_request_minimal(pull_request, True)

			total += issue_count

	print "-"
	out = "%s: %s" % (color_text("Total pull requests", 'display-info-total-title', True), color_text(total, 'display-info-total-count', True))
	print
	display_status()
	return out

def command_merge(repo_name, comment = None):
	"""Merges changes from the local pull request branch into the update-branch and deletes
	the pull request branch"""

	branch_name = get_current_branch_name()
	pull_request_ID = get_pull_request_ID(branch_name)

	update_branch_option = options['update-branch']

	print color_text("Merging %s into %s" % (branch_name, update_branch_option), 'status')
	print

	ret = os.system('git checkout %s' % update_branch_option)
	if ret != 0:
		raise UserWarning("Could not checkout %s" % update_branch_option)

	ret = os.system('git merge %s' % branch_name)
	if ret != 0:
		raise UserWarning("Merge with %s failed. Resolve conflicts, switch back into the pull request branch, and merge again" % update_branch_option)

	print color_text("Deleting branch %s" % branch_name, 'status')
	ret = os.system('git branch -D %s' % branch_name)
	if ret != 0:
		raise UserWarning("Could not delete branch")

	if options['merge-auto-close']:
		print color_text("Closing pull request", 'status')
		close_pull_request(repo_name, pull_request_ID, comment)

	print
	print color_text("Merge completed", 'success')
	print
	display_status()

def command_open(repo_name, pull_request_ID = None):
	"""Open a pull request in the browser"""

	if pull_request_ID is None:
		branch_name = get_current_branch_name()
		pull_request_ID = get_pull_request_ID(branch_name)

	pull_request = get_pull_request(repo_name, pull_request_ID)

	open_URL(pull_request.get('html_url'))

def command_show(repo_name):
	"""List open pull requests

	Queries the github API for open pull requests in the current repo.
	"""

	update_branch_name = options['update-branch']
	filter_by_update_branch = options['filter-by-update-branch']

	if not filter_by_update_branch:
		update_branch_name = "across all branches"
	else:
		update_branch_name = "on branch '%s'" % update_branch_name

	print color_text("Loading open pull requests for %s %s" % (repo_name, update_branch_name), 'status')
	print

	pull_requests = get_pull_requests(repo_name, filter_by_update_branch)

	if len(pull_requests) == 0:
		print "No open pull requests found"

	for pull_request in pull_requests:
		display_pull_request(pull_request)

	display_status()

def command_show_alias(alias):
	""" Shows the username where the alias points to
	"""

	user_item = next((user for user in users.iteritems() if user[0] == alias or user[1] == alias), None)

	if user_item:
		print "The user alias %s points to %s " % user_item
	else:
		print "There is no user alias or github name matching %s in the current mapping file" % alias


def get_pr_stats(repo_name, pull_request_ID):
	if pull_request_ID != None:
		try:
			pull_request_ID = int(pull_request_ID)
			pull_request = get_pull_request(repo_name, pull_request_ID)
		except Exception, e:
			pull_request = pull_request_ID

		display_pull_request_minimal(pull_request)

		branch_name = build_branch_name(pull_request)
		ret = os.system('git show-ref --verify -q refs/heads/%s' % branch_name)

		if ret != 0:
			branch_name = fetch_pull_request(pull_request)

			ret = os.system('git show-ref --verify -q refs/heads/%s' % branch_name)

			if  ret != 0:
				raise UserWarning("Fetch failed")

		merge_base = os.popen('git merge-base %s %s' % (options['update-branch'], branch_name)).read().strip()
		ret = os.system("git --no-pager diff --shortstat {0}..{1} && git diff --numstat --pretty='%H' --no-renames {0}..{1} | xargs -0n1 echo -n | cut -f 3- | sed -e 's/^.*\.\(.*\)$/\\1/' | sort | uniq -c | tr '\n' ',' | sed 's/,$//'".format(merge_base, branch_name))
		print
	else:
		pull_requests = get_pull_requests(repo_name, options['filter-by-update-branch'])

		for pull_request in pull_requests:
			get_pr_stats(repo_name, pull_request)


def command_submit(repo_name, username, reviewer_repo_name = None, pull_body = None, pull_title = None, submitOpenGitHub = True):
	"""Push the current branch and create a pull request to your github reviewer
	(or upstream)"""

	branch_name = get_current_branch_name(False)

	print color_text("Submitting pull request for %s" % branch_name, 'status')

	if reviewer_repo_name is None or reviewer_repo_name == '':
		reviewer_repo_name = get_repo_name_for_remote('upstream')

	if reviewer_repo_name is None or reviewer_repo_name == '':
		raise UserWarning("Could not determine a repo to submit this pull request to")

	if '/' not in reviewer_repo_name:
		reviewer_repo_name = repo_name.replace(username, reviewer_repo_name)

	print color_text("Pushing local branch %s to origin" % branch_name, 'status')

	ret = os.system('git push origin %s' % branch_name)

	if ret != 0:
		raise UserWarning("Could not push this branch to your origin")

	url = get_api_url("repos/%s/pulls" % reviewer_repo_name)

	if pull_title == None or pull_title == '':
		pull_title = build_pull_request_title(branch_name)

	if pull_body == None:
		pull_body = ''

	params = {
		'base': options['update-branch'],
		'head': "%s:%s" % (username, branch_name),
		'title': pull_title,
		'body': pull_body
	}

	print color_text("Sending pull request to %s" % reviewer_repo_name, 'status')

	pull_request = github_json_request(url, params)

	new_pr_url = pull_request.get('html_url')

	if new_pr_url and new_pr_url != '':
		meta('new_pr_url', new_pr_url)

	print
	display_pull_request(pull_request)
	print

	print color_text("Pull request submitted", 'success')
	print
	display_status()

	if submitOpenGitHub:
		open_URL(new_pr_url)

def command_update(repo_name, target = None):
	if target == None:
		branch_name = get_current_branch_name()
	else:
		try:
			pull_request_ID = int(target)
			pull_request = get_pull_request(repo_name, pull_request_ID)
			branch_name = build_branch_name(pull_request)
		except ValueError:
			branch_name = target

	print color_text("Updating %s from %s" % (branch_name, options['update-branch']), 'status')

	update_branch(branch_name)
	print
	display_status()

def command_update_users(filename, url = None, github_users = None, total_pages = 0, all_pages = True):
	if url is None:
		user_organization = options['user-organization']

		if user_organization:
			url = get_api_url("orgs/%s/members" % user_organization)
		else:
			url = get_api_url("repos/%s/forks" % get_repo_name_for_remote("upstream"))

			params = {'per_page': '100', 'sort': 'oldest'}

			url_parts = list(urlparse.urlparse(url))
			query = dict(urlparse.parse_qsl(url_parts[4]))
			query.update(params)

			url_parts[4] = urllib.urlencode(query)

			url = urlparse.urlunparse(url_parts)

	if github_users is None:
		github_users = {}

	items = github_json_request(url)

	m = re.search('[?&]page=(\d)+', url)

	if m is not None and m.group(1) != '':
		print "Doing another request for page: %s of %s" % (m.group(1), total_pages)
	else:
		print "There are %s users, this could take a few minutes..." % len(items)

	user_api_url = get_api_url("users")

	for item in items:
		user_info = item

		if 'owner' in item:
			user_info = item['owner']

		login = user_info['login']

		github_user_info = github_json_request("%s/%s" % (user_api_url, login))
		email = login

		email = get_user_email(github_user_info)

		if email != None:
			github_users[email] = login

	if all_pages:
		link_header = MAP_RESPONSE[url].info().getheader('Link')

		if link_header is not None:
			m = re.search('<([^>]+)>; rel="next",', link_header)

			if m is not None and m.group(1) != '':
				url = m.group(1)

				if total_pages == 0:
					m1 = re.search('<[^>]+[&?]page=(\d+)[^>]+>; rel="last"', link_header)

					if m1 is not None and m1.group(1) != '':
						total_pages = m1.group(1)

				command_update_users(filename, url, github_users, total_pages)

	github_users_file = open(filename, 'w')
	json.dump(github_users, github_users_file)

	github_users_file.close()

	return github_users

def get_user_email(github_user_info):
	email = None

	if 'email' in github_user_info:
		email = github_user_info['email']

		if email != None and email.endswith('@liferay.com'):
			email = email[:-12]

			if email.isdigit():
				email = None
		else:
			email = None

	if email == None:
		if 'name' in github_user_info and ' ' in github_user_info['name']:
			email = github_user_info['name'].lower()
			email = email.replace(' ', '.')
			email = email.replace('(', '.')
			email = email.replace(')', '.')

			email = re.sub('\.+', '.', email)

			# Unicode characters usually do not appear in Liferay emails, so
			# we'll replace them with the closest ASCII equivalent

			email = email.replace(u'\u00e1', 'a')
			email = email.replace(u'\u00e3', 'a')
			email = email.replace(u'\u00e9', 'e')
			email = email.replace(u'\u00f3', 'o')
			email = email.replace(u'\u00fd', 'y')
			email = email.replace(u'\u0107', 'c')
			email = email.replace(u'\u010d', 'c')
			email = email.replace(u'\u0151', 'o')
			email = email.replace(u'\u0161', 's')

	return email

def command_pull(repo_name):
	"""Pulls changes from the remote branch into the local branch of the pull
	request"""

	branch_name = get_current_branch_name()

	print color_text("Pulling remote changes into %s" % branch_name, 'status')

	pull_request_ID = get_pull_request_ID(branch_name)

	pull_request = get_pull_request(repo_name, pull_request_ID)
	repo_url = get_repo_url(pull_request)

	print color_text("Pulling from %s (%s)" % (repo_url, pull_request['head']['ref']), 'status')

	ret = os.system('git pull %s %s' % (repo_url, pull_request['head']['ref']))
	if ret != 0:
		raise UserWarning("Pull failed, resolve conflicts")

	print
	print color_text("Updating %s from remote completed" % branch_name, 'success')
	print
	display_status()

def complete_update(branch_name):
	update_branch_option = options['update-branch']

	if in_work_dir():
		ret = os.system('git checkout %s' % update_branch_option)
		if ret != 0:
			raise UserWarning("Could not checkout %s branch in work directory" % update_branch_option)

		original_dir_path = get_original_dir_path()

		print color_text("Switching to original directory: '%s'" % original_dir_path, 'status')

		os.chdir(original_dir_path)
		chdir(original_dir_path)

		if get_current_branch_name(False) == branch_name:
			ret = os.system('git reset --hard && git clean -f')
			if ret != 0:
				raise UserWarning("Syncing branch %s with work directory failed" % branch_name)
		else:
			ret = os.system('git checkout %s' % branch_name)
			if ret != 0:
				raise UserWarning("Could not checkout %s" % branch_name)

	update_branch_option = options['update-branch']

	branch_treeish = update_meta()

	print
	print color_text("Updating %s from %s complete" % (branch_name, update_branch_option), 'success')

def command_update_meta():
	update_meta()

def continue_update():
	if options['update-method'] == 'merge':
		ret = os.system('git commit')
	elif options['update-method'] == 'rebase':
		ret = os.system('git rebase --continue')

	if ret != 0:
		raise UserWarning("Updating from %s failed\nResolve conflicts and 'git add' files, then run 'gitpr continue-update'" % options['update-branch'])

	# The branch name will not be correct until the merge/rebase is complete
	branch_name = get_current_branch_name()

	complete_update(branch_name)

def display_pull_request(pull_request):
	"""Nicely display_pull_request info about a given pull request"""

	display_pull_request_minimal(pull_request)
	print "	%s" % color_text(pull_request.get('html_url'), 'display-title-url')

	if pull_request.get('body').strip():
		print fill(pull_request.get('body'), initial_indent="	", subsequent_indent="	", width=80)

	# print "   Created: %s" % date.strftime(isodate.parse_datetime( pull_request.get('issue_created_at')), "%B %d, %Y at %I:%M %p")
	# print "   Created: %s" % pull_request.get('issue_created_at')
	# print isodate.parse_datetime( pull_request.get('issue_created_at'), "%Y-%m-%dT%H:%M:%S" )

	print

def display_pull_request_minimal(pull_request, return_text=False):
	"""Display minimal info about a given pull request"""

	text = "%s - %s (%s)" % (color_text("REQUEST %s" % pull_request.get('number'), 'display-title-number', True), color_text(pull_request.get('title'), 'display-title-text', True), color_text(pull_request['user'].get('login'), 'display-title-user'))

	if return_text:
		return text

	print text

def display_status():
	"""Displays the current branch name"""

	branch_name = get_current_branch_name(False)
	out = "Current branch: %s" % branch_name
	print out
	return out

def fetch_pull_request(pull_request):
	"""Fetches a pull request into a local branch, and returns the name of the
	local branch"""

	branch_name = build_branch_name(pull_request)
	repo_url = get_repo_url(pull_request)

	remote_branch_name = pull_request['head']['ref']

	ret = os.system('git fetch %s "%s":%s' % (repo_url, remote_branch_name, branch_name))

	if ret != 0:
		ret = os.system('git show-ref --verify refs/heads/%s' % branch_name)

	if ret != 0:
		raise UserWarning("Fetch failed")

	try:
		os.remove(get_tmp_path('git-pull-request-treeish-%s' % pull_request['number']))
	except OSError:
		pass

	return branch_name

def get_current_branch_name(ensure_pull_request = True):
	"""Returns the name of the current pull request branch"""
	branch_name = os.popen('git rev-parse --abbrev-ref HEAD').read().strip()

	if ensure_pull_request and branch_name[0:13] != 'pull-request-':
		raise UserWarning("Invalid branch: not a pull request")

	return branch_name

def get_default_repo_name():
	repo_name = os.popen('git config github.repo').read().strip()

	# get repo name from origin
	if repo_name is None or repo_name == '':
		repo_name = get_repo_name_for_remote('origin')

	if repo_name is None or repo_name == '':
		raise UserWarning("Failed to determine github repository name")

	return repo_name

def get_git_base_path():
	return os.popen('git rev-parse --show-toplevel').read().strip()

def get_original_dir_path():
	git_base_path = get_git_base_path()

	f = open(os.path.join(get_work_dir(), '.git', 'original_dir_path'), 'rb')
	original_dir_path = f.read()
	f.close()

	if original_dir_path == None or original_dir_path == '':
		config_path = os.readlink(os.path.join(git_base_path, '.git', 'config'))
		original_dir_path = os.path.dirname(os.path.dirname(config_path))

	return original_dir_path

def get_work_dir():
	global _work_dir

	if (_work_dir == None):
		symbolic_ref = os.popen('git symbolic-ref HEAD').read().strip().replace('refs/heads/', '')
		work_dir_global = options['work-dir']

		work_dir_option = None

		if symbolic_ref:
			work_dir_option = 'work-dir-%s' % symbolic_ref

		if work_dir_option:
			_work_dir = os.popen('git config git-pull-request.%s' % work_dir_option).read().strip()
			options[work_dir_option] = _work_dir

		if not _work_dir or not os.path.exists(_work_dir):
			_work_dir = False

		if not _work_dir:
			if work_dir_global and os.path.exists(work_dir_global):
				_work_dir = work_dir_global
			else:
				_work_dir = False

	return _work_dir

def get_pull_request(repo_name, pull_request_ID):
	"""Returns information retrieved from github about the pull request"""

	url = get_api_url("repos/%s/pulls/%s" % (repo_name, pull_request_ID))

	data = github_json_request(url)

	return data

def get_pull_requests(repo_name, filter_by_update_branch=False):
	"""Returns information retrieved from github about the open pull requests on
	the repository"""

	url = get_api_url("repos/%s/pulls" % repo_name)

	pulls = github_json_request(url)

	if filter_by_update_branch:
		update_branch = options['update-branch']

		pull_requests = [pull for pull in pulls if pull['base']['ref'] == update_branch]
	else:
		pull_requests = pulls

	return pull_requests

def get_pull_request_ID(branch_name):
	"""Returns the pull request number of the branch with the name"""

	m = re.search("^pull-request-(\d+)", branch_name)

	pull_request_ID = None

	if m and m.group(1) != '':
		pull_request_ID = int(m.group(1))

	return pull_request_ID

def get_repo_name_for_remote(remote_name):
	"""Returns the repository name for the remote with the name"""

	remotes = os.popen('git remote -v').read()

	m = re.search("^%s[^\n]+?github\.com[^\n]*?[:/]([^\n]+?)\.git" % remote_name, remotes, re.MULTILINE)

	if m is not None and m.group(1) != '':
		return m.group(1)

def get_repo_url(pull_request):
	"""Returns the git URL of the repository the pull request originated from"""

	repo_url = pull_request['head']['repo']['html_url'].replace('https', 'git')
	private_repo = pull_request['head']['repo']['private']

	if private_repo:
		repo_url = pull_request['head']['repo']['ssh_url']

	return repo_url

def get_api_url(command):
	return URL_BASE % command

def get_tmp_path(filename):
	return TMP_PATH % filename

def github_request(url, params = None, authenticate = True):
	if params is not None:
		encode_data = params

		if not isinstance(params, str):
			encode_data = json.dumps(params)

		req = urllib2.Request(url, encode_data)
	else:
		req = urllib2.Request(url)

	if authenticate == 'basic':
		passwd = getpass.getpass("Github password: ").strip()

		auth_string = base64.encodestring('%s:%s' % (auth_username, passwd)).strip()

		authorize_request(req, auth_string, "Basic")
	elif authenticate == True:
		authorize_request(req)

	if DEBUG:
		print url

	try:
		response = urllib2.urlopen(req)
	except urllib2.URLError, msg:
		if authenticate and msg.code == 401 and auth_token:
			print ""
			print color_text('Could not authorize you to connect with Github. Try running "git config --global --unset github.oauth-token" and running your command again to reauthenticate.', 'error')
			print ""

		raise UserWarning("Error communicating with github: \n%s\n%s" % (url, msg))

	data = response.read()

	MAP_RESPONSE[url] = response

	if data == '':
		raise UserWarning("Invalid response from github")

	return data

def github_json_request(url, params = None, authenticate = True):
	data = json.loads(github_request(url, params, authenticate))

	return data

def in_work_dir():
	git_base_path = get_git_base_path()

	work_dir = get_work_dir()

	return git_base_path == work_dir and os.path.islink(os.path.join(git_base_path, '.git', 'config'))

def load_options():
	all_config = os.popen('git config -l').read().strip()
	git_base_path = os.popen('git rev-parse --show-toplevel').read().strip()

	path_prefix = "%s." % git_base_path

	overrides = {}

	matches = re.findall("^git-pull-request\.([^=]+)=([^\n]*)$", all_config, re.MULTILINE)

	for k in matches:
		key = k[0]
		value = k[1]

		if value.lower() in ('f', 'false', 'no'):
			value = False
		elif value.lower() in ('t', 'true', 'yes'):
			value = True
		elif value.lower() in ('', 'none', 'null', 'nil'):
			value = None

		if key.find(path_prefix) == -1:
			options[key] = value
		else:
			key = key.replace(path_prefix, '')
			overrides[key] = value

	options.update(overrides)

def load_users(filename):
	try:
		github_users_file = open(filename, 'r')
	except IOError:
		print "File %s could not be found. Using email names will not be available. Run the update-users command to enable this funcionality" % filename
		return {}

	github_users = json.load(github_users_file)

	github_users_file.close()

	return github_users

def meta(key = None, value = None):
	branch_name = get_current_branch_name(False)

	pull_request_ID = get_pull_request_ID(branch_name)

	val = None

	if pull_request_ID is not None:
		meta_data_path = get_tmp_path('git-pull-request-treeish-%s' % pull_request_ID)

		try:
			f = open(meta_data_path, 'r+')
			current_value = json.load(f)
			current_obj = current_value

			val = current_value

			if key != None:
				pieces = key.split('.')

				key = pieces.pop()

				for word in pieces:
					current_obj = current_obj[word]

				if value == None:
					if key in current_obj:
						val = current_obj[key]
					else:
						val = ''

			if value != None:
				val = value
				current_obj[key] = value
				f.seek(0)
				f.truncate(0)
				json.dump(current_value, f)

			f.close()

			return val

		except Exception, e:
			log("Could not update '%s' with '%s'" % (key, value))



def update_meta():
	branch_name = get_current_branch_name()
	update_branch_option = options['update-branch']
	parent_commit = os.popen('git merge-base %s %s' % (update_branch_option, branch_name)).read().strip()[0:10]
	head_commit = os.popen('git rev-parse HEAD').read().strip()[0:10]

	updated = {
		'parent_commit': parent_commit,
		'head_commit': head_commit
	}

	meta('updated', updated)

	if parent_commit == head_commit:
		branch_treeish = head_commit
	else:
		branch_treeish = '%s..%s' % (parent_commit, head_commit)

	print color_text("Original commits: %s" % branch_treeish, 'status')

	return branch_treeish

def main():
	# parse command line options
	try:
		opts, args = getopt.gnu_getopt(sys.argv[1:], 'hqar:u:l:b:', ['help', 'quiet', 'all', 'repo=', 'reviewer=', 'update', 'no-update', 'user=', 'update-branch=', 'authenticate', 'debug'])
	except getopt.GetoptError, e:
		raise UserWarning("%s\nFor help use --help" % e)

	arg_length = len(args)
	command = "show"

	if arg_length > 0:
		command = args[0]

	if command == 'help':
		command_help()
		sys.exit(0)

	# load git options
	load_options()

	global users, DEFAULT_USERNAME
	global _work_dir
	global DEBUG
	global auth_username, auth_token

	DEBUG = options['debug-mode']

	_work_dir = None

	repo_name = None
	reviewer_repo_name = None

	username = os.popen('git config github.user').read().strip()

	auth_token = os.popen('git config github.oauth-token').read().strip()

	fetch_auto_update = options['fetch-auto-update']

	info_user = username
	submitOpenGitHub = options['submit-open-github']

	# manage github usernames
	users_alias_file = os.popen('git config git-pull-request.users-alias-file').read().strip()

	if len(users_alias_file) == 0:
		users_alias_file = "git-pull-request.users"

	if command != "update-users":
		users = load_users(users_alias_file)

	# process options
	for o, a in opts:
		if o in ('-h', '--help'):
			command_help()
			sys.exit(0)
		elif o in ('-q', '--quiet'):
			submitOpenGitHub = False
		elif o in ('-a', '--all'):
			options['filter-by-update-branch'] = False
		elif o in ('-r', '--repo'):
			if re.search('/', a):
				repo_name = a
			else:
				repo_name = get_repo_name_for_remote(a)
		elif o in ('-b', '--update-branch'):
			options['update-branch'] = a
		elif o in ('-u', '--user', '--reviewer'):
			reviewer_repo_name = a
			info_user = lookup_alias(a)
		elif o == '--update':
			fetch_auto_update = True
		elif o == '--no-update':
			fetch_auto_update = False
		elif o == '--authenticate':
			username = ''
			auth_token = ''
		elif o == '--debug':
			DEBUG = True

	if len(username) == 0:
		username = raw_input("Github username: ").strip()
		os.system("git config --global github.user %s" % username)

	auth_username = username

	if len(auth_token) == 0:
		# Get a list of the current authorized apps and check if we already have a token
		current_oauth_list = github_json_request('https://api.github.com/authorizations', None, 'basic')
		oauth_token = None

		for cur in current_oauth_list:
			if cur['note'] == SCRIPT_NOTE:
				oauth_token = cur['token']

		# If we don't have a token, let's create one
		if not oauth_token:
			oauth_data = github_json_request(
				'https://api.github.com/authorizations',
				'{"scopes": ["repo"],"note": "%s"}' % SCRIPT_NOTE,
				'basic'
			)

			oauth_token = oauth_data['token']

		if oauth_token:
			auth_token = oauth_token
			os.system("git config --global github.oauth-token %s" % oauth_token)
		else:
			raise UserWarning('Could not authenticate you with Github')

	# get repo name from git config
	if repo_name is None or repo_name == '':
		repo_name = get_default_repo_name()

	if (not reviewer_repo_name) and (command == 'submit'):
		reviewer_repo_name = os.popen('git config github.reviewer').read().strip()

	if reviewer_repo_name:
		reviewer_repo_name = lookup_alias(reviewer_repo_name)

		if command != "submit":
			repo_name = reviewer_repo_name + '/' + repo_name.split('/')[1]

	DEFAULT_USERNAME = username

	# process arguments
	if command == 'show':
		command_show(repo_name)
	elif arg_length > 0:
		if command == 'alias':
			if arg_length >= 2:
				command_alias(args[1], args[2], users_alias_file)
		elif command == 'close':
			if arg_length >= 2:
				comment = args[1]
				pull_request_ID = comment

				if comment.isdigit():
					comment = ''

					if arg_length == 3:
						comment = args[2]

					print color_text("Closing pull request", 'status')
					close_pull_request(repo_name, pull_request_ID, comment)
				else:
					command_close(repo_name, comment)
			else:
				command_close(repo_name)
		elif command in ('continue-update', 'cu'):
			command_continue_update()
		elif command == 'fetch':
			command_fetch(repo_name, args[1], fetch_auto_update)
		elif command == 'fetch-all':
			command_fetch_all(repo_name)
		elif command == 'help':
			command_help()
		elif command == 'info':
			command_info(info_user)
		elif command == 'info-detailed':
			command_info(info_user, True)
		elif command == 'merge':
			if arg_length >= 2:
				command_merge(repo_name, args[1])
			else:
				command_merge(repo_name)
		elif command == 'open':
			if arg_length >= 2:
				command_open(repo_name, args[1])
			else:
				command_open(repo_name)
		elif command == 'pull':
			command_pull(repo_name)
		elif command == 'update-meta':
			command_update_meta()
		elif command == 'submit':
			pull_body = None
			pull_title = None

			if arg_length >= 2:
				pull_body = args[1]

			if arg_length >= 3:
				pull_title = args[2]

			command_submit(repo_name, username, reviewer_repo_name, pull_body, pull_title, submitOpenGitHub)
		elif command == 'update':
			if arg_length >= 2:
					command_update(repo_name, args[1])
			else:
				command_update(repo_name, options['update-branch'])
		elif command == 'update-users':
			command_update_users(users_alias_file)
		elif command == 'show-alias':
			if arg_length >= 2:
				command_show_alias(args[1])
		elif command == 'stats' or args[0] == 'stat':
			pull_request_ID = None

			if arg_length >= 2:
				pull_request_ID = args[1]

			get_pr_stats(repo_name, pull_request_ID)
		else:
			command_fetch(repo_name, args[0], fetch_auto_update)

def lookup_alias(key):
	user_alias = key

	try:
		if users and (key in users) and users[key]:
			user_alias = users[key]
	except Exception, e:
		pass

	return user_alias

def open_URL(url):
	if (os.popen('command -v open').read().strip() != ''):
		ret = os.system('open -g "%s" 2>/dev/null' % url)

		if ret != 0:
			os.system('open "%s"' % url)

	elif (os.popen('command -v cygstart').read().strip() != ''):
		os.system('cygstart "%s"' % url)

def post_comment(repo_name, pull_request_ID, comment):
	url = get_api_url("repos/%s/issues/%s/comments" % (repo_name, pull_request_ID))
	params = {'body': comment}

	github_json_request(url, params)

def update_branch(branch_name):
	if in_work_dir():
		raise UserWarning("Cannot perform an update from within the work directory.\nIf you are done fixing conflicts run 'gitpr continue-update' to complete the update.")

	work_dir = get_work_dir()

	if work_dir:
		original_dir_path = get_git_base_path()

		print color_text("Switching to work directory %s" % work_dir, 'status')
		os.chdir(work_dir)

		f = open(os.path.join(work_dir, '.git', 'original_dir_path'), 'wb')
		f.write(original_dir_path)
		f.close()

		ret = os.system('git reset --hard && git clean -f')
		if ret != 0:
			raise UserWarning("Cleaning up work directory failed, update not performed")

	ret = os.system('git checkout %s' % branch_name)
	if ret != 0:
		if work_dir:
			raise UserWarning("Could not checkout %s in the work directory, update not performed" % branch_name)
		else:
			raise UserWarning("Could not checkout %s, update not performed" % branch_name)

	update_branch_option = options['update-branch']

	ret = os.system('git %(update-method)s %(update-branch)s' % (options))

	if ret != 0:
		if work_dir:
			chdir(work_dir)
		raise UserWarning("Updating %s from %s failed\nResolve conflicts and 'git add' files, then run 'gitpr continue-update'" % (branch_name, update_branch_option))

	complete_update(branch_name)


def log(*args):
	for arg in args:
		print json.dumps(arg, sort_keys=True, indent=4)
		print "/---"

if __name__ == "__main__":
	try:
		main()
	except UserWarning, e:
		print color_text(e, 'error')
		sys.exit(1)
