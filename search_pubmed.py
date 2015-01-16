#!/usr/bin/env python2.7

import urllib, urllib2, urlparse
from xml.etree import ElementTree
import sys

URLBASE = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
UID_FACE = 'esearch.fcgi'
SUMM_FACE = 'esummary.fcgi'
ABST_FACE = 'efetch.fcgi'

class NoRedirect(urllib2.HTTPErrorProcessor):

	def http_response(self,  req,  resp):
		return resp

def get_doi_link(doiterm):

	urlbase = 'http://dx.doi.org'
	h_accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
	h_accept_lang = 'en-US,en;q=0.5'
	h_conn = 'keep-alive'
	h_host = 'dx.doi.org'
	h_referer = 'http://www.doi.org/'
	h_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:31.0) Gecko/20100101 Firefox/31.0'
	h_accept_enc = 'gzip, deflate'
	h_cookie = None
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

		resp = noreopener.open(req)

		post_data = None
		if resp.code in (301, 302, 303):
			cookie = '; '.join(j[1].rstrip()
				for j in (i.split(": ",1) 
					for i in resp.headers.headers ) if j[0]=='Set-Cookie')
			if cookie != '':
				h_cookie = cookie
			else:
				h_cookie = None

			location = [j[1].rstrip()
					for j in (i.split(": ",1) 
						for i in resp.headers.headers ) if j[0]=='Location']
			h_host = urlparse.urlparse(location[0]).netloc
			urlbase = location[0]
		else:
			break

	resp.close()
	return resp.url

def get_uid(term):

	tree = ElementTree.parse(
			urllib2.urlopen(URLBASE + UID_FACE, 
			urllib.urlencode({
				'db':'pubmed', 
				'term': term
				})))

	return [i.text for i in tree.findall('.//IdList/Id')]

def get_summary(*uid):

	tree = ElementTree.parse(
			urllib2.urlopen(URLBASE + SUMM_FACE,
			urllib.urlencode({
				'db':'pubmed',
				'version':'2.0',
				'id': ','.join(uid)})))

	return tree

def parse_paper(etree):

	def check_node(node):
		if node is None:
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

	tree = ElementTree.parse(
			urllib2.urlopen(URLBASE + ABST_FACE,
			urllib.urlencode({
				'db':'pubmed',
				'rettype':'xml', 
				'id': ','.join(str(i) for i in term)})))

	for i in tree.findall('.//PubmedArticle'):
		abstract = [ j.text for j in i.findall('.//Article/Abstract/AbstractText')]
		loc = i.find('.//Article/ELocationID')
		if loc is not None and loc.attrib['EIdType'] == 'doi':
			eloc = loc.text
		else:
			eloc = ''
		yield (''.join(abstract), eloc)

def get_pub_link(*term):

	tree = ElementTree.parse(
			urllib2.urlopen(URLBASE + ABST_FACE,
			urllib.urlencode({
				'db':'pubmed',
				'rettype':'xml', 
				'id': ','.join(str(i) for i in term)})))

	for i in tree.findall('PubmedArticle//Article/ElocationID'):
		abstract = [ j.text for j in i.findall('AbstractText')]
		yield ''.join(abstract)

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
			print 'ISSN: '.ljust(padding), 
			print result['issn']
			print 'ESSN: '.ljust(padding), 
			print result['essn']

		if verbose > 4:
			print 'Link: '.ljust(padding), 
			print result['link']

		if verbose > 1:
			print 'Abstract:\n    ', 
			print result['abstract']
	
	print

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-v', '--verbose', action='count', dest='verb')
	parser.add_argument('TERM', nargs=1)

	args = parser.parse_args()

	term = args.TERM[0].strip().replace('\n', ' ')

	if not term:
		raise SystemExit

	result = parse_paper(get_summary(*get_uid(term)))

	if args.verb > 1:
		pmids = [p['pmid'] for p in result]
		for idx, a in enumerate(get_abstract(*pmids)):
			result[idx]['abstract'] = a[0]
			if args.verb > 4:
				result[idx]['link'] = get_doi_link(a[1])
			else:
				result[idx]['link'] = a[1]

	for i in result: print_info(i, args.verb)
