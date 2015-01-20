#!/usr/bin/env python2.7

import urllib, urllib2, urlparse
from xml.etree import ElementTree
import sys
import re
from contextlib import closing
import HTMLParser

URLBASE = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
UID_FACE = 'esearch.fcgi'
SUMM_FACE = 'esummary.fcgi'
ABST_FACE = 'efetch.fcgi'

class NoRedirect(urllib2.HTTPErrorProcessor):

	def http_response(self,  req,  resp):
		return resp

class __MedsciParser(HTMLParser.HTMLParser):
	issn_ptn = re.compile(r'^\d{4}-\d{3}[\dX]$')
	next_will_be = False
	if_ = -1
	def handle_data(self, data):
		data = data.strip()
		if not self.next_will_be:
			if self.issn_ptn.match(data):
				self.next_will_be = True
		else:
			if data:
				self.if_ = float(data)

def get_impact_factor(title='', issn=''):
	if not title and not issn:
		return 0

	searchurl = 'http://www.medsciediting.com/sci/?action=search'
	param = {'fullname':title, 
			'issn':issn, 
			'impact_factor_b':'', 
			'impact_factor_s':'', 
			'rank':'number_rank_b', 
			'Sumit':'Search'}
	req = urllib2.Request(searchurl)
	req.add_header('host', 'www.medsciediting.com')
	req.add_header('referer', 'http://www.medsciediting.com/sci/?action=search')
	req.add_data(urllib.urlencode(param))

	medsci = __MedsciParser()
	try:
		with closing(urllib2.urlopen(req)) as resp:
			for line in resp:
				if medsci.if_ < 0:
					medsci.feed(line)
	except HTMLParser.HTMLParseError:
		return 0
	else:
		return medsci.if_

def get_doi_link(doiterm):

	urlbase = 'http://dx.doi.org'
	h_accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
	h_accept_lang = 'en-US,en;q=0.5'
	h_conn = 'keep-alive'
	h_host = 'dx.doi.org'
	h_referer = 'http://www.doi.org/'
	h_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:31.0) Gecko/20100101 Firefox/31.0'
	h_accept_enc = 'gzip, deflate'
	h_cookie = ''
	post_data = urllib.urlencode({'hdl':doiterm})

	noreopener = urllib2.build_opener(NoRedirect)

	while True:
		req = urllib2.Request(urlbase)
		req.add_header('Accept-Language',h_accept_lang)
		req.add_header('Accept-Encoding', h_accept_enc)
		req.add_header('Connection',h_conn)
		req.add_header('Host',h_host)
		req.add_header('Referer',h_referer)
		req.add_header('User-Agent',h_ua)
		if post_data is not None:
			req.add_data(post_data)
		if h_cookie is not None:
			req.add_header('Cookie', h_cookie)


		with closing(noreopener.open(req)) as resp:
			post_data = None
			if resp.code in (301, 302, 303):
				cookie = resp.headers.getheader('set-cookie')
				if cookie is not None:
					if h_cookie != '':
						h_cookie += '; '+cookie
					else:
						h_cookie = cookie

				location = resp.headers.getheader('location')
				h_host = urlparse.urlparse(location).netloc
				urlbase = location
			else:
				break

	return resp.url

def get_uid(term):
	with closing(urllib2.urlopen(URLBASE + UID_FACE, 
			urllib.urlencode({ 'db':'pubmed', 'term': term }))) as resp:
		tree = ElementTree.parse(resp)
	return [i.text for i in tree.findall('.//IdList/Id')]

def get_summary(*uid):

	with closing(urllib2.urlopen(URLBASE + SUMM_FACE,
			urllib.urlencode({ 'db':'pubmed', 'version':'2.0',
				'id': ','.join(uid)}))) as resp:
		tree = ElementTree.parse(resp)
	return tree

def parse_paper(etree):

	def check_node(node):
		if node is None:
			return ''
		elif node.text is None:
			return ''
		else:
			return node.text

	summ = [ dict(
		pmid = i.attrib['uid'], 
		title = check_node(i.find('Title')), 
		pubdate = check_node(i.find('PubDate')), 
		epubdate = check_node(i.find('EPubDate')), 
		source = check_node(i.find('Source')), 
		volume = check_node(i.find('Volume')), 
		authors = [j.find('Name').text for j in i.findall('Authors/Author')], 
		issue = check_node(i.find('Issue')), 
		issn = check_node(i.find('ISSN')), 
		essn = check_node(i.find('ESSN')), 
		pages = check_node(i.find('Pages')))
		for i in etree.findall('.//DocumentSummarySet/DocumentSummary')
		]

	return summ

def get_abstract(*term):
	'''retrieving all the abstract and doi location of papers for given PMID'''
	
	with closing(urllib2.urlopen(URLBASE + ABST_FACE,
			urllib.urlencode({ 'db':'pubmed', 'rettype':'xml', 
				'id': ','.join(str(i) for i in term)}))) as resp:
		tree = ElementTree.parse(resp)

	for i in tree.findall('.//PubmedArticle'):
		abstract = [ j.text for j in i.findall('.//Article/Abstract/AbstractText')]
		loc = i.find('.//Article/ELocationID')
		if loc is not None and loc.attrib['EIdType'] == 'doi':
			eloc = loc.text
		else:
			eloc = ''
		yield (''.join(abstract), eloc)

def print_info(result,verbose=0):

	padding = 10

	print 'PMID: '.ljust(padding), 
	print result['pmid']
	print 'Title: '.ljust(padding), 
	print result['title']

	if verbose > 0:
		print 'Journal: '.ljust(padding), 
		print result['source']
		print 'Authors: '.ljust(padding), 
		print ', '.join(result['authors'])
		print 'PubDate: '.ljust(padding), 
		print result['pubdate']

		if verbose > 2:
			print 'Volume: '.ljust(padding), 
			print result['volume']
			print 'Issue: '.ljust(padding), 
			print result['issue']
			print 'Pages: '.ljust(padding), 
			print result['pages']

		if verbose > 3:
			if result['issn']:
				print 'ISSN: '.ljust(padding), 
				print result['issn']
			if result['essn']:
				print 'ESSN: '.ljust(padding), 
				print result['essn']
			if result['link']:
				print 'Link: '.ljust(padding), 
				print result['link']

		if verbose > 5:
			if result['if']:
				print 'IF: '.ljust(padding), 
				print result['if']

		if verbose > 1:
			print 'Abstract:\n    ', 
			print result['abstract']
	
	print

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
# more '-v's are supplied,  more detailed info given.
	parser.add_argument('-v', '--verbose', action='count', dest='verb')
# if the count of results exceeds the limit, the progress aborts.
	parser.add_argument('-l', '--limit', type=int, default=20, dest='limit')
	parser.add_argument('TERM', nargs=1)

	args = parser.parse_args()

	term = args.TERM[0].strip().replace('\n', ' ')

	if not term:
		raise SystemExit

	uids = get_uid(term)

	if len(uids) > args.limit :
		raise SystemExit('More than {0} results returned, consider using more specific terms', args.limit)

	result = parse_paper(get_summary(*get_uid(term)))

	if args.verb > 1:
		pmids = [p['pmid'] for p in result]
		for idx, a in enumerate(get_abstract(*pmids)):
			result[idx]['abstract'] = a[0]
			if args.verb > 4 and a[1]:
				try:
					result[idx]['link'] = get_doi_link(a[1])
# if retrieving link from doi is waiting too long, user can cancel this.
				except KeyboardInterrupt:
					result[idx]['link'] = a[1]
			else:
				result[idx]['link'] = a[1]
	
			if args.verb > 5:
				result[idx]['if'] = get_impact_factor(title=result[idx]['source'], issn=result[idx]['issn'])

	for i in result: print_info(i, args.verb)

