#!/usr/bin/env python

from __future__ import print_function

import itertools
import argparse
import json
import sys
import re
import os
from getpass import getpass
from ConfigParser import SafeConfigParser

def toto():
        print("tutu")


def main():
	# Import non-standard modules
	try:
		import requests
	except ImportError:
		sys.exit("Python module 'requests' not found.\nPlease install using: pip install requests")

	try:
		from pyquery import PyQuery as pq
	except ImportError:
		sys.exit("Python module 'pyquery' not found.\nPlease install using: pip install pyquery")

	# Support both 2.x and 3.x
	try:
		input = raw_input
	except NameError:
		pass
	
	# Helper functions
	def strip(s):
		return re.sub(r'[\s\xa0]+', ' ', s).strip() # \xa0 is &nbsp;

	def encode(html):
		return unicode(html).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')
	
	def verbose(s):
		if args.verbose:
			print(s, file=sys.stderr)

        def load_items(id_page):
                items = []
	        for page in itertools.count(1):
		        verbose('Retrieving page %d...' % page)
                
		        r = session.get('https://www.bricklink.com/v2/wanted/search.page?type=A&wantedMoreID=%d&sort=1&pageSize=100&page=%d' % (id_page, page))
                        #verbose(r.text)
                        if not r:
			        sys.exit('Could not retrieve page %d of part list.' % page)
                        
		        verbose('Parsing.')

		        match = re.search(r'var wlJson = (\{.+?\});\r?\n', r.text, re.MULTILINE)
		        if not match:
			        sys.exit('Unexpected wanted page format.')

		        try:
			        data = json.loads(match.group(1))
		        except:
			        sys.exit('Invalid JSON found in wanted page.')

		        # Assert expected data
		        if not isinstance(data, dict) or not isinstance(data.get('wantedItems'), list):
			        sys.exit('Unexpected JSON content in wanted page.')

		        if not data['wantedItems']:
			        # No items on this page
			        break

		        items += data['wantedItems']

		        if len(items) == data.get('totalResults'):
			        break

                return items

        def export(items, out):
		out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
		out.write('<!DOCTYPE BrickStockXML>\n')
		out.write('<BrickStockXML>\n')
		out.write('<Inventory>\n')
		for item in items:
			out.write('\t<Item>\n')
			out.write('\t\t<ItemID>%s</ItemID>\n' % item['itemNo'])
			out.write('\t\t<ItemTypeID>%s</ItemTypeID>\n' % item['itemType'])
			out.write('\t\t<ColorID>%d</ColorID>\n' % item['colorID'])
			out.write('\t\t<ItemName>%s</ItemName>\n' % encode(item['itemName']))
			out.write('\t\t<ColorName>%s</ColorName>\n' % item['colorName'])
			out.write('\t\t<Qty>%d</Qty>\n' % item['wantedQty'])
			out.write('\t\t<Price>%s</Price>\n' % (item['wantedPrice'] if item['wantedPrice'] > 0 else '0\n'))
			out.write('\t\t<Condition>%s</Condition>\n' % item['wantedNew'])
			out.write('\t</Item>\n')
		out.write('</Inventory>\n')
		out.write('</BrickStockXML>\n')

	
	# Command arguments
	parser = argparse.ArgumentParser(description='Export a BrickLink wanted list.')
	parser.add_argument('--version', action='version', version='bricklink-export 1.2')
	parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False, help='be verbose')
	parser.add_argument('-u', '--username', dest='username', help='username on BrickLink')
	parser.add_argument('-p', '--password', dest='password', help='password on BrickLink (omit for prompt)')
	parser.add_argument('-l', '--list', dest='list', action='store_true', default=False, help='list of wanted lists')
	parser.add_argument('-c', '--colors', dest='colors', action='store_true', default=False, help='list of colors')
	parser.add_argument('-e', '--export', dest='export', metavar='ID', type=int, help='wanted list to export')
        parser.add_argument('-a', '--all', dest='all', help='Export all lists in files at a given location. The file names are given by the list names.')
	args = parser.parse_args()
	
	# Requests session
	session = requests.Session()
	session.headers.update({'User-Agent': 'bricklink-export 1.2 (http://github.com/fdev/bricklink-export)'})
	
	# List and export require authentication
	if args.list or args.export or args.all is not None:
		username = args.username
		password = args.password
		
		# Credentials file
		config = SafeConfigParser()
		config.read([os.path.expanduser('~/.bricklink-export.conf'), os.path.expanduser('~/bricklink-export.ini')])

		# Look for username in config file if not given
		if not username:
			try:
				username = config.get('user', 'username')
				verbose('Read username from config file: %s' % username)
			except:
				pass
			
		# Request username if not given
		if not username:
			verbose('No username specified.')
			try:
				username = input('Enter username: ')
			except KeyboardInterrupt:
				sys.exit(1)

		# Look for password in config file if not given
		if not password:
			try:
				password = config.get('user', 'password')
				verbose('Read password from config file.')
			except:
				pass
			
		# Request password if not given
		if not password:
			verbose('No password specified.')
			try:
				password = getpass('Enter password: ')
			except KeyboardInterrupt:
				sys.exit(1)

		# Authenticate
		verbose('Authenticating.')
		payload = {
			'pageId': 'LOGIN',
			'userid': username,
			'password': password,
		}
		r = session.post('https://www.bricklink.com/ajax/renovate/login.ajax', data=payload, allow_redirects=False)

		if not r:
			sys.exit('Could not log in to BrickLink.')

		try:
			data = json.loads(r.text)
		except:
			sys.exit('Invalid JSON in authentication response.')


		if data.get('returnCode') != 0:
			sys.exit('Invalid username or password specified.')

		verbose('Authenticated as %s.' % username)

	# Color list
	if args.colors:
		verbose('Retrieving color guide.')
		r = session.get('https://www.bricklink.com/catalogColors.asp')
		if not r:
			sys.exit('Could not retrieve color guide.')

		verbose('Parsing.')
		html = pq(r.text)
		tables = html('table tr')

		colors = []
		for table in map(pq, tables):
			if len(table('td')) == 9 and strip(table('td:nth-child(9)').text()) != 'Color Timeline':
				id = strip(table('td:nth-child(1)').text())
				name = strip(table('td:nth-child(4)').text())

				if not id.isdigit() or not name:
					sys.exit('Unexpected color guide format.')

				colors.append({
					'id': id,
					'name': name,
				})

		print('ID\tName')
		for color in colors:
			print('%s\t%s' % (color['id'], color['name']))
		sys.exit()
	
	# List of wanted lists
	if args.list:
		verbose('Retrieving list of wanted lists.')
		r = session.get('https://www.bricklink.com/v2/wanted/list.page')
		if not r:
			sys.exit('Could not retrieve wanted lists.')

		verbose('Parsing.')

		match = re.search(r'var wlJson = (\{.+?\});\r?\n', r.text, re.MULTILINE)
		if not match:
			sys.exit('Unexpected wanted list page format.')

		try:
			data = json.loads(match.group(1))
		except:
			sys.exit('Invalid JSON found in wanted list page.')

		# Assert expected data
		if not isinstance(data, dict) or not isinstance(data.get('wantedLists'), list):
			sys.exit('Unexpected JSON content in wanted list page.')

		# Print list
		print('ID\tItems\tName')
		for row in data['wantedLists']:
			print('%s\t%s\t%s' % (row['id'], row['num'], row['name']))
	
		sys.exit()

        # Get all the wanted lists
        if args.all:
                verbose('Retrieving list of wanted lists.')
		r = session.get('https://www.bricklink.com/v2/wanted/list.page')
		if not r:
			sys.exit('Could not retrieve wanted lists.')

		verbose('Parsing.')

		match = re.search(r'var wlJson = (\{.+?\});\r?\n', r.text, re.MULTILINE)
		if not match:
			sys.exit('Unexpected wanted list page format.')

		try:
			data = json.loads(match.group(1))
		except:
			sys.exit('Invalid JSON found in wanted list page.')

		# Assert expected data
		if not isinstance(data, dict) or not isinstance(data.get('wantedLists'), list):
			sys.exit('Unexpected JSON content in wanted list page.')

		# Store wanted lists in a list
                wl_list = []
                for row in data['wantedLists']:
			wl_list.append({'id':row['id'], 'num':row['num'], 'name':row['name']})
                for wl in wl_list:
                        items = load_items(wl["id"])
                        verbose("Exporting " + wl['name'])
                        f = open(args.all + "/" + wl['name'] + '.bsx', 'w')
                        export(items, f)
                        f.close()
                        
                sys.exit()
                
	# Export
	if args.export is not None:
                items = load_items(args.export)
                export(items, sys.stdout)
		sys.exit()
	
	parser.print_help()

if __name__ == '__main__':
	main()

