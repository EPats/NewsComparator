import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse

# List of bbc elements. Eventually this will be a mapping between source and targets.
RSS_ELEMENTS = {'linked_title': 'title', 'linked_desc': 'description', 'url': 'link', 'publication_date': 'pubDate'}


def get_rss_feeds_from_json_file(filepath: str) -> []:
    with open(filepath, 'r') as file:
        json_data = json.load(file)
    return json_data['rss_feeds']


def get_articles_list(rss_url: str) -> [{}]:
    articles = []
    r = requests.get(rss_url)
    soup = BeautifulSoup(r.content, 'xml')
    source_title = soup.find('title').text
    for item in soup.find_all('item'):
        article = {'source_title': source_title}
        for element in RSS_ELEMENTS:
            if item.find(RSS_ELEMENTS[element]):
                article[element] = item.find(RSS_ELEMENTS[element]).text
        articles.append(article)
    return articles


def get_article2(article: {}) -> {}:
    url = article['url']
    article_dict = article
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    domain = urlparse(url).netloc.removeprefix('www.')
    if domain in ARTICLE_FUNCTIONS:
        article_dict.update(ARTICLE_FUNCTIONS[domain](soup))
    else:
        print(f'No scraping function found for {domain}')
    return article_dict


def get_article_content_bbc(soup: BeautifulSoup) -> {}:
    article_details = {}
    article_body = soup.find(attrs={'id': 'main-content'})
    if article_body:
        article_title = article_body.find(attrs={'id': 'main-heading'})
        if article_title:
            article_details['article_title'] = article_title.text
        # related?
        video_block = article_body.find(attrs={'data-component': 'video-block'})
        if video_block:
            fig_caption = video_block.find('figcaption')
            if fig_caption:
                article_details['fig_caption'] = fig_caption.find('p').text
        byline_block = article_body.find(attrs={'data-component': 'byline-block'})
        if byline_block:
            article_details['byline'] = byline_block.text
        text_blocks = article_body.find_all(attrs={'data-component': 'text-block'})
        bold_text = [text_block.text for text_block in text_blocks if text_block.find('b')]
        reg_text = [text_block.text for text_block in text_blocks if text_block.text not in bold_text]
        article_details['bold'] = bold_text
        article_details['text'] = reg_text
        if topic_list := article_body.find(attrs={'data-component': 'topic-list'}):
            if topic_list_title := topic_list.find('h2'):
                article_details['list_title'] = topic_list_title.text
            for i, list_item in enumerate(topic_list.find_all('li')):
                article_details[f'list_item_{i}'] = list_item.text
                article_details[f'list_item_{i}_link'] = list_item.find('a')['href']
    return article_details


def get_article_content_telegraph(soup: BeautifulSoup) -> {}:
    article_details = {}
    article_body = soup.find(attrs={'id': 'main-content'})
    if article_body:
        header = article_body.find('header')
        if header:
            article_title = header.find('h1')
            if article_title:
                article_details['article_title'] = article_title.text
            article_subtitle = header.find('p')
            if article_subtitle:
                article_details['article_subtitle'] = article_subtitle.text
            # related?
        video_block = article_body.find(attrs={'data-component': 'video-block'})
        if video_block:
            fig_caption = video_block.find('figcaption')
            if fig_caption:
                article_details['fig_caption'] = fig_caption.find('p').text
        byline_block = article_body.find_all(attrs={'class': 'e-byline__author'})
        if byline_block:
            article_details['byline'] = [author.text for author in byline_block]
        text_blocks = article_body.find_all(attrs={'itemprop': 'articleBody'})
        bold_text = [text_block.text for text_block in text_blocks if text_block.find('b')]
        reg_text = [text_block.text for text_block in text_blocks if text_block.text not in bold_text]
        article_details['bold'] = bold_text
        article_details['text'] = reg_text
        if topic_list := soup.find(attrs={'class': 'articleList section'}):
            if topic_list_title := topic_list.find(attrs={'class': 'article-list__heading'}):
                article_details['list_title'] = topic_list_title.text
            for i, list_item in enumerate(topic_list.find_all(attrs={'class': 'list-headline'})):
                article_details[f'list_item_{i}'] = list_item.text
                article_details[f'list_item_{i}_link'] = list_item.find('a')['href']
    return article_details


ARTICLE_FUNCTIONS = {'bbc.co.uk': get_article_content_bbc,
                     'telegraph.co.uk': get_article_content_telegraph}

all_articles = []
#urls = get_rss_feeds_from_json_file('param.json')
urls = [ "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://feeds.bbci.co.uk/news/uk/rss.xml",
    "https://www.telegraph.co.uk/rss.xml" ]

for url in urls:
    all_articles += get_articles_list(url)

# print(json.dumps(all_articles, indent=4))

article_data = []
for article in all_articles:
    if 'url' in article:
        article_data.append(get_article2(article))

with open('data2.json', 'w') as outfile:
    outfile.write(json.dumps(article_data, indent=4))